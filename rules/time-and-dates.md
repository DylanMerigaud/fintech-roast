# Time and dates

Part of the [fintech-roast](../README.md) rulebook. See [README.md](README.md) for the format contract and severity scale.

## TIM-1: Financial period calculations run in server-local or mixed time zones

**Severity**: high

**What to detect**

- SQL columns typed `timestamp` / `timestamp without time zone` (or MySQL `DATETIME`) holding instants that later feed period math; grep DDL for `timestamp` not followed by `with time zone` / not `timestamptz`, and MySQL `DATETIME` used where `TIMESTAMP` semantics are intended.
- Local-time getters used to derive a period bucket: JS `getFullYear/getMonth/getDate/getHours` (instead of `getUTC*` or `Intl.DateTimeFormat` with an explicit `timeZone`), Python `datetime.now()` / `datetime.today()` / `.date()` on a naive datetime, `date.today()` for cutoffs.
- Java/Kotlin `LocalDate.now()`, `LocalDateTime.now()`, `new Date()`, or `Calendar.getInstance()` with no `ZoneId`; Go `time.Now()` without a `*time.Location`; Ruby `Time.now` / `Date.today` and `Time.parse` without a zone.
- Statement-cutoff, accrual-period, or due-date logic that truncates or buckets a stored instant with no explicit business zone argument (e.g. `date_trunc('month', ts)` on a `timestamp` column, `GROUP BY` on a local-time date).
- Server code that assumes `TZ` / the OS locale defines the accounting calendar; period boundaries move when the deploy region or `TimeZone` GUC changes.

**Why it breaks**

An instant is a single point on the global timeline, but a financial period (a statement month, an accrual window, a due date) is a wall-clock concept that only exists relative to a specific zone. When you store instants correctly but then compute the period in the server's local zone (or in a mix of zones), a transaction near midnight lands in a different month depending on where the process runs, so cutoffs, accruals, and due dates shift silently. PostgreSQL's own docs note that `timestamp with time zone` is stored as UTC with the input zone discarded ("the value is stored internally as UTC, and the originally stated or assumed time zone is not retained"), and that a fixed numeric offset default makes it "impossible to adapt to daylight-saving time when doing date/time arithmetic across DST boundaries". JavaScript's `Date` likewise exposes two method families (local vs UTC) so the same instant yields a different day depending on which you call. Get the zone wrong and revenue is booked into the wrong period or an invoice is dated a day off.

**Fix**

Store instants as UTC (`timestamptz` in Postgres, `Instant` / epoch elsewhere) and never derive a business period in the ambient server zone. Compute every cutoff, accrual window, and due date in the one explicit business zone that the contract or entity defines (e.g. `America/New_York` for a US statement), passing it as an argument. Treat the business zone as data on the account, not an implicit global, and keep the boundary between "instant" (machine) and "local date" (human) explicit in the type system so a naive local datetime can never silently stand in for an instant.

```sql
-- Bucket in the account's business zone, never the server's:
SELECT date_trunc('month', ts AT TIME ZONE 'America/New_York') AS period
FROM ledger_entries;
```

```python
# Python: capture the instant as aware-UTC, derive the period in the account's business zone.
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

now = datetime.now(timezone.utc)                 # aware instant, never datetime.now() (naive, server-local)
biz_zone = ZoneInfo(account.business_zone)       # e.g. "America/New_York", data on the account
period = now.astimezone(biz_zone).strftime("%Y-%m")   # the statement month is a wall-clock concept
```

```java
// Java: store the instant, derive the period in the account's business zone (never LocalDateTime.now()).
Instant now = Instant.now();                                 // a point on the timeline, persist this
ZoneId bizZone = ZoneId.of(account.getBusinessZone());       // "America/New_York", data on the account
YearMonth period = YearMonth.from(now.atZone(bizZone));      // the statement month is wall-clock, in the biz zone
// LocalDateTime.now() has no zone: it cannot name an instant and silently uses the server's clock.
```

**False positives**

- The whole system is genuinely single-zone by design (one jurisdiction, one exchange, one accounting calendar) and that zone is pinned explicitly and enforced, not inherited from the host locale.
- Displaying an already-computed instant in the viewer's local zone for UI purposes is correct; the rule targets period / cutoff arithmetic, not presentation.
- A stored `timestamp without time zone` (or naive datetime) that legitimately represents a floating wall-clock value with no instant meaning (e.g. "store opens at 09:00 local wherever the store is"), where the zone is applied later per row.

**Sources**

1. [PostgreSQL Documentation: Date/Time Types](https://www.postgresql.org/docs/current/datatype-datetime.html) (PostgreSQL Global Development Group)
2. [Don't Do This: Don't use timestamp (without time zone)](https://wiki.postgresql.org/wiki/Don't_Do_This) (PostgreSQL wiki)
3. [Date - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date) (Mozilla MDN Web Docs)
4. [Noda Time: Core concepts](https://nodatime.org/2.4.x/userguide/concepts) (Noda Time, Jon Skeet et al.)
5. [datetime, Basic date and time types](https://docs.python.org/3/library/datetime.html) (Python Software Foundation)
6. [java.time package summary (Instant, LocalDateTime, ZonedDateTime)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/time/package-summary.html) (Oracle)

## TIM-2: DST-naive day arithmetic (86400 s per day, epoch-ms division)

**Severity**: high

**What to detect**

- Literal day math: `* 86400`, `* 86400000`, `86_400`, `* 24 * 60 * 60`, `1000*60*60*24`, or dividing an epoch-millis / seconds difference by one of these to get "days between".
- `Date.now()` / `getTime()` subtraction converted to days; Python `(a-b).total_seconds()/86400`; Java `Instant` / epoch millis diff divided by 86400000 instead of `ChronoUnit.DAYS.between` on zoned values.
- Python: `dt + timedelta(days=1)` on an aware datetime used to mean "next calendar day" (a `timedelta` is a fixed 86400 s duration, so it lands on the wrong wall-clock hour across a DST transition), or `timedelta(days=n)` added to iterate accrual days in a DST zone; `(a - b).days` / `(a - b).total_seconds() / 86400` on aware datetimes to count calendar days between them instead of `(a.date() - b.date()).days`.
- Adding a calendar amount by adding a fixed `Duration`: Noda Time `Duration.FromDays` / `Plus(Duration...)` on a `ZonedDateTime`, java.time `Instant.plus(Duration.ofDays(n))` where a `Period` / `plusDays` on a `ZonedDateTime` was meant, Go `t.Add(24*time.Hour)` used to mean "next day".
- Daily accrual / interest or usage-metering loops that assume every day contributes exactly 1/365 (or a fixed second-count), computed over local days in a DST zone.
- Any accumulation of a fixed increment over a long uptime without periodic resync (fixed-point or float tick counters that drift); grep for hand-rolled `seconds += 0.1`-style timers.

**Why it breaks**

In every zone that observes DST, one day per year is 23 hours long and one is 25 hours long, so "a day" is not 86400 seconds and adding 24 hours is not adding a calendar day. Noda Time's guide is explicit: arithmetic on a `ZonedDateTime` runs on the underlying timeline, so "twenty minutes after 1:45am could easily be 1:05am" at a fall-back transition, and MDN notes `getTimezoneOffset()` varies with the date precisely because of DST. Divide an epoch-ms difference by 86400000 across a spring-forward boundary and a full local day counts as 0.958 days; a daily accrual, a "days overdue" figure, or a proration then comes out short or long. The Patriot missile failure at Dhahran ([GAO IMTEC-92-26](https://www.gao.gov/products/imtec-92-26)) is the canonical time-representation drift: multiplying a tenths-of-a-second clock by a 24-bit fixed-point 1/10 truncated a tiny error that grew to about 0.34 s over roughly 100 hours of uptime, enough to miss the target and let a Scud strike a barracks (28 dead). It is not a money bug, but it shows exactly how a fixed-increment time accumulation drifts.

**Fix**

Separate timeline arithmetic (`Duration`, fixed seconds) from calendar arithmetic (`Period`, days / months) and use the calendar kind for anything a human calls "a day". Count days with calendar-aware APIs on zoned or local dates: `ChronoUnit.DAYS.between(d1,d2)`, `LocalDate` differences, Noda Time `Period.Between`, Python `(d1.date()-d2.date()).days`, never an epoch-difference divide. To add days across a DST boundary, add a `Period` / `plusDays` on a `ZonedDateTime` (or convert to `LocalDate`, add, reconvert once, resolving ambiguous / skipped times deliberately), not a `Duration`. For daily accruals, iterate calendar days and apply the contractual per-day factor rather than pro-rating by seconds. For long-running counters, resync against a monotonic authoritative clock instead of summing a fixed tick.

```python
# Python: count and add days on calendar dates, not by dividing or adding a fixed 86400 s.
from datetime import date, timedelta

days_overdue = (date.today() - invoice.due_date).days   # date arithmetic is DST-immune, unlike total_seconds()/86400

# "Next calendar day" is a date step, applied to the local date, not dt + timedelta(days=1) on an aware datetime.
next_day = local_date + timedelta(days=1)                # safe: `date` has no clock, so no DST hour to shift
for accrual_day in (invoice.start + timedelta(days=n) for n in range((invoice.end - invoice.start).days)):
    balance += principal * daily_rate                    # iterate calendar days, do not pro-rate by seconds
```

```java
// Java: count and add days as a calendar amount (Period), not a fixed Duration / epoch divide.
long daysOverdue = ChronoUnit.DAYS.between(invoice.getDueDate(), LocalDate.now(bizZone));  // LocalDate diff

ZonedDateTime nextDay = day.plusDays(1);                 // Period-based: keeps the wall-clock across DST
// wrong: day.plus(Duration.ofDays(1)) adds exactly 24h, landing on the wrong hour at a DST transition
```

**False positives**

- You genuinely want elapsed physical time (SLA seconds, latency, rate limits, TTLs, token expiry): 86400 s per day is correct because you mean 24 hours, not a calendar day.
- All timestamps are UTC-only and the domain never crosses a DST zone (e.g. a system that reasons purely in UTC days); epoch-ms division by 86400000 for UTC days is exact.
- Zones with no DST for the entire data range (much of Asia, or most of Mexico post-2022 excluding the northern-border municipalities and Baja California that kept US-schedule DST) where every local day is 24 h, though this is fragile if the zone set can change and is better handled with calendar APIs anyway.

**Sources**

1. [Noda Time: Date and time arithmetic](https://nodatime.org/2.4.x/userguide/arithmetic) (Noda Time, Jon Skeet et al.)
2. [Date.prototype.getTimezoneOffset() | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date/getTimezoneOffset) (Mozilla MDN Web Docs)
3. [Patriot Missile Defense: Software Problem Led to System Failure at Dhahran, Saudi Arabia (GAO IMTEC-92-26)](https://www.gao.gov/products/imtec-92-26) (U.S. General Accounting Office)
4. [The Patriot Missile Failure](https://www-users.cse.umn.edu/~arnold/disasters/patriot.html) (Douglas N. Arnold, University of Minnesota)
5. [java.time package summary (Period versus Duration)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/time/package-summary.html) (Oracle)

## TIM-3: Ambiguous billing/statement period boundaries and month-end clamping

**Severity**: critical

**What to detect**

- Period range predicates mixing inclusive and exclusive ends: `ts BETWEEN start AND end` (BETWEEN is inclusive on both sides) for adjacent periods, or `>= start AND <= end` where the next period also uses `>= end`, double-counting or dropping the boundary row.
- Both `<= period_end` on one query and `>= period_end` (or `= period_end`) on the neighbor; grep for period filters that are not the half-open `[start, next_start)` shape.
- Naive month rollover that can throw or clamp inconsistently: `date.setMonth(m+1)` in JS (Jan 31 to Mar 3), Python `date.replace(month=...)` without day clamping, Java `plusMonths` vs manual day math, `AddDate(0,1,0)` in Go normalizing Jan 31 to Mar 3.
- Anniversary / anchor logic that stores a `day_of_month` and indexes into a shorter month without falling back to the last valid day (Feb 30 / 31, Apr 31).
- Proration or statement code that recomputes the boundary independently on two sides (charge side vs credit side) rather than deriving both from one canonical `[start, end)` interval.

**Why it breaks**

A period boundary transaction is real money, and if the closing edge is inclusive in one place and the opening edge of the next period is also inclusive, the boundary transaction is billed twice; if both are exclusive, it is dropped. Month-end anchoring compounds this: naive `+1 month` on Jan 31 overflows to Mar 3 in most date libraries, so a January statement can swallow all of February or skip it. Stripe documents the intended contract precisely: a monthly subscription anchored to January 31 bills "February 28 (or February 29 in a leap year), March 31, April 30", and `day_of_month = 31` renews "on the last day of that month" when a month is shorter. That is deliberate clamping, not overflow. Get either wrong on a production billing path and customers are double-charged or under-charged, and statements fail to reconcile.

**Fix**

Model every billing / statement period as a half-open interval `[start, next_start)` and use it consistently, so each transaction belongs to exactly one period with no gap and no overlap; never use inclusive `BETWEEN` for adjacent ranges. Derive both the charge and credit sides from the same interval object rather than recomputing each end. For month-end anchors, clamp explicitly to the last valid day of the target month (matching the documented Jan 31 to Feb 28/29 to Mar 31 behavior) and add tests for Jan 31, Feb 29 leap years, and 30-day months.

```sql
-- One period, no overlap, no gap:
WHERE ts >= period_start AND ts < next_period_start
-- month-end anchor: clamp, do not overflow
-- target_day = min(anchor_day, days_in_month(y, m))
```

```python
# Python: half-open period test, and month rollover that clamps instead of overflowing.
import calendar
from dateutil.relativedelta import relativedelta

in_period = period_start <= ts < next_period_start   # [start, next_start), never BETWEEN (inclusive both ends)

# relativedelta clamps Jan 31 + 1 month to Feb 28/29 rather than overflowing to Mar 3.
next_start = period_start + relativedelta(months=1)
# Anchor logic without dateutil: clamp the stored day_of_month to the target month's length.
last_day = calendar.monthrange(year, month)[1]       # 28/29/30/31
anchor = date(year, month, min(day_of_month, last_day))
```

```java
// Java: half-open period test, and month rollover that clamps (java.time already clamps).
boolean inPeriod = !ts.isBefore(periodStart) && ts.isBefore(nextPeriodStart);  // [start, next), never BETWEEN

// LocalDate.plusMonths clamps Jan 31 + 1 month to Feb 28/29 (docs: last valid day), not overflow.
LocalDate nextStart = periodStart.plusMonths(1);
// explicit anchor: clamp the stored dayOfMonth to the target month's length.
YearMonth ym = YearMonth.of(year, month);
LocalDate anchor = ym.atDay(Math.min(dayOfMonth, ym.lengthOfMonth()));   // 28/29/30/31
```

**False positives**

- `BETWEEN` (or a closed interval) on a whole-day date-only column where the next period starts on a strictly later day and boundaries cannot collide, so inclusivity is unambiguous.
- A product spec that intentionally treats the anchor differently (e.g. always bill the 28th to avoid month-end entirely, or a mid-month anchor that never hits a short month) where clamping is moot.
- Reporting / analytics queries where a one-row boundary overlap is acceptable and documented (non-money views), as opposed to invoicing or ledger paths.

**Sources**

1. [Set the subscription billing renewal date | Stripe Documentation](https://docs.stripe.com/billing/subscriptions/billing-cycle) (Stripe)
2. [java.time package summary (Java SE 21)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/time/package-summary.html) (Oracle)
3. [java.time.LocalDate.plusMonths (day-of-month clamping)](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/time/LocalDate.html) (Oracle)

## TIM-4: Interest day-count convention ignored or hardcoded

**Severity**: high

**What to detect**

- Interest computed as `principal * rate * days / 365` (or `/360`, or `/365.25`) with the denominator and day-count rule baked in as a literal instead of read from the instrument / contract.
- Python: `principal * rate * (end - start).days / 365` (or `/ 360`) with the divisor hardcoded and `(end - start).days` (a bare actual day count) fed to it regardless of the instrument's convention; a module-level `DAYS_IN_YEAR = 365`; no `DayCount` enum / `convention` field on the loan model, so two instruments on different bases cannot be represented.
- A single `daysBetween` used for accrual with no notion of a convention parameter; grep for `/ 360`, `/ 365`, `* rate *` near a day difference, and for a hardcoded `DAYS_IN_YEAR`.
- Actual day counts (calendar `daysBetween`) paired with a 360 denominator, or 30/360 assumed without the ISDA day-of-month adjustments (Jan 31 / Feb-end special cases) implemented.
- No enum / config for the convention (ACT/360, ACT/365F, ACT/ACT, 30/360, 30E/360) on the loan, bond, or swap record; the code cannot represent that two instruments accrue differently.
- Cross-period accrual that sums sub-period fractions under a 30/360 rule (which is not additive), producing a total that differs from a single full-period computation.

**Why it breaks**

The day-count convention is a contractual term, not an implementation detail, and different conventions yield materially different interest on the same principal, rate, and dates. ACT/360 uses the actual day count over a 360 denominator, so it produces a larger fraction than a 30/360 basis for the same period; Wikipedia's day-count article notes the borrower effectively pays interest for 5 to 6 extra days a year under ACT/360 versus the 30/360 day-count convention. 30/360 uses 30-day months with specific day-of-month adjustments (OpenGamma Strata: 30/360 ISDA computes `(360*deltaYear + 30*deltaMonth + deltaDay)/360` and changes day-of-month 31 to 30 in defined cases), and unlike actual methods it is not additive across sub-periods. There is no central authority; ISDA and ICMA document the variants (ISDA's 2006 Definitions cover both 30/360 and 30E/360). Hardcode one denominator and you compute the wrong interest for any instrument on a different basis, which is a compliance and money-correctness exposure.

**Fix**

Make the day-count convention an explicit attribute of each instrument (an enum like ACT_360, ACT_365F, ACT_ACT_ISDA, THIRTY_360_ISDA, THIRTY_E_360) sourced from the contract, and compute the year fraction through a convention object, not an inline divide (`accrual = notional * rate * dayCountFraction(convention, start, end)`). Prefer a vetted library (OpenGamma Strata `DayCounts`, QuantLib) over hand-rolling the 30/360 day-of-month adjustments, which are easy to get subtly wrong. Because 30/360 is not additive, compute each coupon period against its own endpoints rather than summing daily fractions, and add golden-value tests per convention (including a leap-year ACT/ACT case and a Jan 31 / Feb-end 30/360 case). Never let a default denominator stand in for the contractual basis.

```python
# Python: the convention is data on the instrument; the year fraction goes through a convention object.
from decimal import Decimal
from enum import Enum

class DayCount(Enum):
    ACT_360 = "ACT/360"
    ACT_365F = "ACT/365F"
    THIRTY_360_ISDA = "30/360 ISDA"     # among others: ACT/ACT, 30E/360

def year_fraction(convention: DayCount, start, end) -> Decimal:
    ...   # delegate to a vetted library (QuantLib / Strata); do not hand-roll the 30/360 adjustments

# accrual reads the instrument's own convention, never a hardcoded /365 or /360.
accrual = loan.notional * loan.rate * year_fraction(loan.day_count, period_start, period_end)
```

**False positives**

- A closed system where every instrument is contractually the same single convention (e.g. a product that only ever issues ACT/365F loans in one jurisdiction), and that convention is asserted / tested rather than accidental.
- Non-interest uses of a `/365` or `/360` factor (annualizing a metric, a display APR approximation, back-of-envelope estimates) that never post money to a ledger.
- A deliberately simplified simple-interest quote or preview clearly labeled as an estimate, where the authoritative accrual is computed elsewhere with the correct convention.

**Sources**

1. [DayCounts (OpenGamma Strata API docs)](https://strata.opengamma.io/apidocs/com/opengamma/strata/basics/date/DayCounts.html) (OpenGamma)
2. [30/360 Day Count Conventions](https://www.isda.org/2008/12/22/30-360-day-count-conventions/) (International Swaps and Derivatives Association)
3. [Day count convention](https://en.wikipedia.org/wiki/Day_count_convention) (Wikipedia)
