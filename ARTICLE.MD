# Building iki-dq-check: A Data Quality Tool for Python Workflows

_A look at how I designed `iki-dq-check`: a Python framework with 25
checks across 3 validation tiers._

---

There's a moment most data engineers eventually run into.

A dashboard number looks wrong. You trace it through transformation
logic, through ingestion jobs, through warehouse models, and eventually
end up at the source. Somewhere along the way, something quietly went
wrong: a null value appeared where it shouldn't, duplicate rows slipped
through, a date column became a string column, or a source table changed
shape without warning.

The dashboard is usually where the issue becomes visible, but the
problem started much earlier.

I built **iki-dq-check** because I wanted a cleaner way to catch these
problems before they reached downstream systems.

`iki-dq-check` is a Python library and CLI tool for validating data
quality. It includes:

- **25 checks**
- **3 progressive validation tiers**
- A **single interface** for different data formats
- Python-native configuration
- Programmatic pipelines and CLI workflows

The goal wasn't to replace every existing framework. The goal was to
create something that felt natural to use in day-to-day Python
workflows.

---

## The Problem With Data Quality Tooling

Most approaches I used fell somewhere between two extremes.

### Heavyweight systems

Comprehensive frameworks can provide a large set of capabilities, but
they may also introduce configuration layers, additional setup, and
workflow overhead.

That trade-off can make sense in large environments, but sometimes the
setup process becomes larger than the validation itself.

### Lightweight scripts

The opposite approach usually looks like this:

```python
assert df["email"].notnull().all()
assert df["salary"].min() >= 0
```

This works initially.

But over time:

- checks become scattered
- error messages become harder to interpret
- logic gets duplicated
- pipeline integration becomes difficult

I wanted something in between: structured enough for production
workflows, while remaining simple enough to use in notebooks, scripts,
and CI environments.

---

## Architecture: Three Validation Tiers

Not every dataset needs the same level of validation.

An exploratory notebook probably doesn't require cross-system
consistency checks. A financial reporting pipeline probably does.

`iki-dq-check` organizes checks into progressive tiers.

### 🟢 Lite Tier

Core checks intended as a baseline:

- `NullCheck`
- `PrimaryKeyCheck`
- `DuplicateRowCheck`
- `DataTypeCheck`
- `NumericRangeCheck`

These are the checks I would generally want running on almost every
dataset.

---

### 🟡 Standard Tier

The next layer focuses on business rules and operational logic:

- `RegexCheck`
- `DomainCheck`
- `BusinessRuleCheck`
- `CrossColumnCheck`
- `FreshnessCheck`
- `VolumeCheck`
- `OutlierCheck`
- `ReferentialIntegrityCheck`

These checks start moving beyond structural validation into data meaning
and expectations.

---

### 🔵 Advanced Tier

The final tier focuses on larger production concerns:

- `SchemaDriftCheck`
- `DuplicateFileIngestionCheck`
- `HierarchyCheck`
- `AuditColumnCheck`
- `CrossSystemConsistencyCheck`
- `ReferenceDataCheck`
- `ChecksumCheck`
- `DistributionCheck`
- `NegativeValueCheck`
- `PercentageTotalCheck`
- `StringLengthCheck`
- `CompletenessCheck`

Running higher tiers automatically includes lower-tier checks.

For example:

```bash
iki-dq-check --tier advanced
```

runs all checks from Lite and Standard as well.

---

## CLI Workflow

I wanted the CLI experience to remain straightforward.

Running validations should not require writing application code.

```bash
# Install
pip install -e .

# Show available checks
iki-dq-check --list

# Run Lite tier
iki-dq-check --tier lite --file data.json --config my_config.py

# Save results
iki-dq-check --tier standard --file data.csv --config my_config.py --output report.json

# Execute specific checks
iki-dq-check --check NullCheck --check PrimaryKeyCheck --file data.json

# Stop on first critical issue
iki-dq-check --tier lite --file data.json --config my_config.py --fail-fast
```

The CLI output includes:

- check status
- severity level
- summary statistics
- pass rate
- failed validation details

---

## Python-Native Configuration

I wanted configuration to remain part of the Python workflow rather than
moving entirely into external files.

`DQConfig` uses typed dataclasses:

```python
from Iki_DQ_Check.config import DQConfig

config = DQConfig(
    pk_column="order_id",
    ranges={
        "amount": (0, None),
        "quantity": (1,10000),
    },
    allowed={
        "status": [
            "pending",
            "fulfilled",
            "cancelled"
        ]
    },
)
```

Using Python also makes more complex validation easier:

```python
rules={
    "fulfilled_has_date":
    lambda r:
    r.get("status") != "fulfilled"
    or r.get("completed_at") is not None
}
```

---

## One Interface Across Multiple Formats

For library users, most interactions happen through a single facade
function.

```python
from Iki_DQ_Check import check

report = check(df, tier="standard", config=cfg)

report = check(
    pl.scan_parquet("warehouse/*.parquet"),
    tier="lite",
    config=cfg
)

report = check(
    conn.sql("SELECT * FROM orders"),
    tier="advanced",
    config=cfg
)

report = check(
    "orders.parquet",
    tier="lite",
    config=cfg
)
```

The goal is to keep the interface consistent regardless of where the
data originates.

The caller shouldn't need to think about internal normalization steps.

---

## Pipeline API

For orchestration systems and automated workflows, checks can also be
composed directly.

```python
pipeline = (
    DataQualityPipeline("orders_daily")
    .add(NullCheck())
    .add(PrimaryKeyCheck())
    .add(FreshnessCheck())
)

report = pipeline.run(data)

if report.success_rate < 1:
    raise RuntimeError("Quality gate failed")
```

Instead of immediately raising exceptions, the pipeline captures
failures and returns them through a report object.

That approach makes it easier to integrate with:

- Airflow
- CI pipelines
- scheduled jobs
- custom orchestration systems

---

## Extending With Custom Checks

I also wanted extension points to stay simple.

Creating a new check only requires subclassing `DataCheck` and
implementing `run()`.

```python
class CorporateEmailCheck(DataCheck):

    def run(self,data,email_column="email",**_):

        violations=[
            r for r in data
            if "@corp.com"
            not in str(
                r.get(email_column,"")
            )
        ]

        if violations:
            return self._fail(
                "Found invalid emails"
            )

        return self._pass(
            "Passed"
        )
```

Custom checks can then be registered and reused like built-in checks.

---

## Testing

The project currently includes **220 tests** covering:

- validation checks
- pipeline behavior
- registry logic
- loaders
- facade functionality
- CLI workflows

A few implementation details surfaced during testing.

### Empty pipeline behavior

Initially, an empty pipeline automatically created default checks.

That behavior turned out to be confusing because an empty pipeline
should remain empty.

The fix was moving default construction logic into the CLI layer instead
of the core pipeline itself.

### Missing test resources

Some CLI integration tests referenced files that had never been added to
the project structure.

Once those files were included, failures became easier to diagnose and
the tests reflected real usage scenarios more accurately.

---

## Areas I'm Exploring Next

A few ideas I'm interested in exploring:

- HTML report generation
- Native Airflow operator support
- GitHub Actions integration
- Parallel execution for independent checks
- richer reporting and visualization

---

## Closing Thoughts

One thing I learned while building this project is that data quality
issues are usually small when they begin.

A single null value or duplicate row rarely looks serious in isolation.

The challenge is that those issues compound as data moves through
systems.

`iki-dq-check` started as an attempt to make those checks easier to
organize and easier to reuse across different workflows.

If you've built something similar or have ideas for improvements, I'd be
interested to hear them.

---

`iki-dq-check` is MIT licensed and available on GitHub.
