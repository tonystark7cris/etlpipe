# Preparation Overview
Provides data cleansing, filtering, sorting, sampling, formula evaluation, and other row/column transformations, mirroring the visual ETL tool Preparation tool palette.

---

## Function: `filter`
**Description**: Splits a DataFrame into two parts based on matching and non-matching rows against a condition.

### Signature
`def filter(df: pd.DataFrame, condition: str | Callable[[pd.DataFrame], pd.Series] | None = None, *, column: str | None = None, operator: str | None = None, value: Any = None) -> tuple[pd.DataFrame, pd.DataFrame]`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: The input DataFrame to filter.
  * **Valid Input Range/Format**: Any valid DataFrame.
* **condition** | **str | Callable | None** | **Optional** | **None**
  * **Description**: A pandas query string or a callable returning a boolean Series.
  * **Valid Input Range/Format**: Example: `"Age > 30"` or `lambda d: d["Age"] > 30`.
* **column** | **str | None** | **Optional** | **None**
  * **Description**: The column to filter by when using Basic filter mode.
  * **Valid Input Range/Format**: A valid column name in `df`.
* **operator** | **str | None** | **Optional** | **None**
  * **Description**: The operator to apply in Basic filter mode.
  * **Valid Input Range/Format**: `"=="`, `"!="`, `">"`, `">="`, `"<"`, `"<="`, `"contains"`, `"does not contain"`, `"is null"`, `"is not null"`, `"is empty"`, `"is not empty"`, `"is true"`, `"is false"`.
* **value** | **Any** | **Optional** | **None**
  * **Description**: The value to compare against in Basic filter mode.
  * **Valid Input Range/Format**: Compatible scalar value for the target column.

### Returns (Outputs)
* **Type**: `tuple[pd.DataFrame, pd.DataFrame]`
* **Description**: A tuple containing `(true_df, false_df)`, matching visual ETL tool's T and F anchors.

### Exceptions & Errors
* `ValueError`: Raised if neither `condition` nor basic filter arguments are provided, or if an unsupported operator is passed.

### Behavior & Edge Cases
Null values typically route to `false_df` unless specifically matched with `is null`. String comparisons like `contains` behave correctly.

### Usage Examples
1. **Basic Usage**:
   ```python
   t, f = Preparation.filter(df, "Age > 30")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   t, f = Preparation.filter(df, column="City", operator="==", value="Boston")
   ```

---

## Function: `formula`
**Description**: Creates or updates a column using an expression evaluated across rows.

### Signature
`def formula(df: pd.DataFrame, column: str, expression: str | Callable[[pd.DataFrame], pd.Series]) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: The input DataFrame.
* **column** | **str** | **Required** | **None**
  * **Description**: Name of the column to create or update.
* **expression** | **str | Callable** | **Required** | **None**
  * **Description**: A Python expression string or a callable lambda function.
  * **Valid Input Range/Format**: Pandas query eval strings or `lambda d: d["A"] + d["B"]`.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A new DataFrame containing the computed column.

### Exceptions & Errors
* `ValueError`: Raised if an unsafe string evaluation (like `print()`) is attempted.

### Behavior & Edge Cases
Spaces in column names in string expressions are safely transpiled (e.g., automatically backticked for evaluation). Does not mutate the original DataFrame.

### Usage Examples
1. **Basic Usage**:
   ```python
   df2 = Preparation.formula(df, "DoubleSalary", "Salary * 2")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   df2 = Preparation.formula(df, "UpperName", lambda d: d["Name"].str.upper())
   ```

---

## Function: `select`
**Description**: Selects, renames, and changes data types for columns.

### Signature
`def select(df: pd.DataFrame, columns: Sequence[str] | None = None, renames: dict[str, str] | None = None, dtypes: dict[str, str | type] | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: The input DataFrame.
* **columns** | **Sequence[str] | None** | **Optional** | **None**
  * **Description**: Columns to keep, in the specified order. `None` keeps all columns.
* **renames** | **dict[str, str] | None** | **Optional** | **None**
  * **Description**: Mapping of `{old_name: new_name}` to rename columns.
* **dtypes** | **dict[str, str | type] | None** | **Optional** | **None**
  * **Description**: Mapping of `{column: dtype}` applied *after* renaming.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A new DataFrame with the requested schema changes.

### Exceptions & Errors
None explicitly defined (pandas may raise `KeyError` if invalid columns are referenced).

### Behavior & Edge Cases
Columns omitted from `columns` are dropped. Renames happen before dtype casting.

### Usage Examples
1. **Basic Usage**:
   ```python
   df2 = Preparation.select(df, columns=["Name", "Age"])
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   df2 = Preparation.select(df, renames={"Name": "FullName"}, dtypes={"Age": "float64"})
   ```

---

## Function: `data_cleansing`
**Description**: Cleans string data values by stripping whitespace, removing punctuation, or modifying casing, and handles nulls.

### Signature
`def data_cleansing(df: pd.DataFrame, columns: Sequence[str] | None = None, remove_null_rows: bool = False, replace_nulls_with: Any | None = None, strip_whitespace: bool = True, remove_letters: bool = False, remove_numbers: bool = False, remove_punctuation: bool = False, modify_case: str | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **columns** | **Sequence[str] | None** | **Optional** | **None**
  * **Description**: Columns to clean. If `None`, defaults to all string columns.
* **remove_null_rows** | **bool** | **Optional** | **False**
  * **Description**: If true, drops rows where *any* selected column is null.
* **replace_nulls_with** | **Any | None** | **Optional** | **None**
  * **Description**: Fills nulls with this value before string operations.
* **strip_whitespace** | **bool** | **Optional** | **True**
  * **Description**: Removes leading/trailing whitespace.
* **remove_letters** | **bool** | **Optional** | **False**
  * **Description**: Removes all alphabetic characters.
* **remove_numbers** | **bool** | **Optional** | **False**
  * **Description**: Removes all digit characters.
* **remove_punctuation** | **bool** | **Optional** | **False**
  * **Description**: Removes punctuation marks.
* **modify_case** | **str | None** | **Optional** | **None**
  * **Description**: Modifies text case. Valid options: `"lower"`, `"upper"`, `"title"`.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A cleaned DataFrame.

### Exceptions & Errors
None specifically raised by the function.

### Behavior & Edge Cases
Operates only on the requested string columns. If a non-string column is provided, string-specific methods are safely ignored or bypassed depending on pandas types.

### Usage Examples
1. **Basic Usage**:
   ```python
   clean = Preparation.data_cleansing(df, strip_whitespace=True)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   clean = Preparation.data_cleansing(df, columns=["Text"], remove_punctuation=True, modify_case="lower")
   ```

---

## Function: `sort`
**Description**: Sorts a DataFrame by one or more columns in specified directions.

### Signature
`def sort(df: pd.DataFrame, columns: str | Sequence[str], ascending: bool | Sequence[bool] = True) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: The input DataFrame.
* **columns** | **str | Sequence[str]** | **Required** | **None**
  * **Description**: Column or list of columns to sort by.
* **ascending** | **bool | Sequence[bool]** | **Optional** | **True**
  * **Description**: Sort direction. A single boolean applies to all; a list must match the length of `columns`.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A sorted DataFrame.

### Exceptions & Errors
None explicitly defined (pandas handles invalid column names).

### Behavior & Edge Cases
Missing (null) values default to pandas sorting logic (usually put at the end).

### Usage Examples
1. **Basic Usage**:
   ```python
   sorted_df = Preparation.sort(df, "Age", ascending=False)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   sorted_df = Preparation.sort(df, ["Region", "Sales"], ascending=[True, False])
   ```

---

## Function: `unique`
**Description**: Splits data into two DataFrames containing unique and duplicate rows based on specified columns.

### Signature
`def unique(df: pd.DataFrame, columns: str | Sequence[str], ignore_case: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: The input DataFrame.
* **columns** | **str | Sequence[str]** | **Required** | **None**
  * **Description**: Column(s) used to evaluate uniqueness.
* **ignore_case** | **bool** | **Optional** | **False**
  * **Description**: If true, treats string cases equally (e.g., "A" == "a").

### Returns (Outputs)
* **Type**: `tuple[pd.DataFrame, pd.DataFrame]`
* **Description**: A tuple containing `(unique_df, duplicate_df)`, matching U and D anchors. The first occurrence is unique, subsequent occurrences are duplicates.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
If `ignore_case` is True, strings are temporarily case-normalized for the uniqueness check, but original values are preserved in the outputs.

### Usage Examples
1. **Basic Usage**:
   ```python
   uniq, dups = Preparation.unique(df, "Email")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   uniq, dups = Preparation.unique(df, "City", ignore_case=True)
   ```

---

## Function: `sample`
**Description**: Samples a subset of rows from the DataFrame.

### Signature
`def sample(df: pd.DataFrame, n: int | None = None, pct: float | None = None, random: bool = False, position: str = "first", random_state: int | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **n** | **int | None** | **Optional** | **None**
  * **Description**: Number of rows to sample.
* **pct** | **float | None** | **Optional** | **None**
  * **Description**: Fraction of rows to sample (between 0.0 and 1.0).
* **random** | **bool** | **Optional** | **False**
  * **Description**: If True, rows are randomly sampled.
* **position** | **str** | **Optional** | **"first"**
  * **Description**: Sample from the `"first"` or `"last"` rows. Ignored if `random=True`.
* **random_state** | **int | None** | **Optional** | **None**
  * **Description**: Seed for reproducible random sampling.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A DataFrame containing the sampled subset.

### Exceptions & Errors
* `ValueError`: Raised if both `n` and `pct` are provided, or if neither is provided.

### Behavior & Edge Cases
When sampling randomly, exact numbers or percentages are handled cleanly even for small DataFrames.

### Usage Examples
1. **Basic Usage**:
   ```python
   top5 = Preparation.sample(df, n=5)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   rand_10pct = Preparation.sample(df, pct=0.10, random=True, random_state=42)
   ```

---

## Function: `record_id`
**Description**: Appends an auto-incrementing ID column to the DataFrame.

### Signature
`def record_id(df: pd.DataFrame, column_name: str = "RecordID", start: int = 1) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **column_name** | **str** | **Optional** | **"RecordID"**
  * **Description**: Name of the new ID column.
* **start** | **int** | **Optional** | **1**
  * **Description**: Starting integer value for the ID sequence.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A DataFrame with the ID column prepended as the first column.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Values increment sequentially regardless of the DataFrame's current index.

### Usage Examples
1. **Basic Usage**:
   ```python
   df = Preparation.record_id(df)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   df = Preparation.record_id(df, "RowNum", start=100)
   ```

---

## Function: `generate_rows`
**Description**: Generates new rows of data programmatically using a callable expression.

### Signature
`def generate_rows(count: int, expression: Callable[[int], dict[str, Any]] | None = None, columns: Sequence[str] | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **count** | **int** | **Required** | **None**
  * **Description**: Number of rows to generate.
* **expression** | **Callable | None** | **Optional** | **None**
  * **Description**: A function taking the row index (0 to count-1) and returning a dictionary of column values.
* **columns** | **Sequence[str] | None** | **Optional** | **None**
  * **Description**: Enforces specific column ordering on the returned data.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A new DataFrame containing the generated rows.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
If `expression` is None, generates a single column `RowNum` with values from `0` to `count-1`.

### Usage Examples
1. **Basic Usage**:
   ```python
   df = Preparation.generate_rows(5)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   df = Preparation.generate_rows(5, lambda i: {"x": i, "y": i**2})
   ```

---

## Function: `auto_field`
**Description**: Optimizes data types across the DataFrame to save memory.

### Signature
`def auto_field(df: pd.DataFrame) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A DataFrame with downcasted integers/floats and low-cardinality strings converted to categoricals.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
String columns with < 50% unique values are cast to pandas `category` types. Numeric data is squeezed to the smallest possible width (e.g., int8, int16).

### Usage Examples
1. **Basic Usage**:
   ```python
   optimized = Preparation.auto_field(df)
   ```
2. **Advanced Usage/Edge Cases**:
   (Same as basic, behavior scales based on data volume automatically)

---

## Function: `multi_field_formula`
**Description**: Applies a function across multiple columns simultaneously.

### Signature
`def multi_field_formula(df: pd.DataFrame, columns: Sequence[str], expression: Callable[[pd.Series], pd.Series]) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **columns** | **Sequence[str]** | **Required** | **None**
  * **Description**: Columns to apply the expression to.
* **expression** | **Callable** | **Required** | **None**
  * **Description**: Function mapping a pandas Series to a modified Series.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A DataFrame with the transformed columns updated in place.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
The provided expression must be vectorized or handle pandas Series correctly. Modifies columns in parallel.

### Usage Examples
1. **Basic Usage**:
   ```python
   df = Preparation.multi_field_formula(df, ["Age", "Salary"], lambda s: s * 2)
   ```

---

## Function: `multi_row_formula`
**Description**: Creates or updates a column based on values in adjacent (previous/next) rows.

### Signature
`def multi_row_formula(df: pd.DataFrame, column: str, expression: Callable[[pd.Series, pd.Series], pd.Series], rows_back: int = 1, group_by: str | Sequence[str] | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **column** | **str** | **Required** | **None**
  * **Description**: Name of the column to compute/update.
* **expression** | **Callable** | **Required** | **None**
  * **Description**: Function accepting `(current_series, shifted_series)` and returning the computed result Series.
* **rows_back** | **int** | **Optional** | **1**
  * **Description**: Offset for shifting. Positive values look back, negative values look forward.
* **group_by** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Evaluates offsets independently within grouped partitions.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: DataFrame with the calculated multi-row column.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Boundary conditions (e.g., the first row looking back) result in NaNs being passed into the expression for the shifted series.

### Usage Examples
1. **Basic Usage**:
   ```python
   df = Preparation.multi_row_formula(df, "Delta", lambda cur, prev: cur - prev, rows_back=1)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   df = Preparation.multi_row_formula(df, "Delta", lambda c, p: c - p, rows_back=1, group_by="Group")
   ```

---

## Function: `tile`
**Description**: Bins/quantiles data into groups based on numerical values.

### Signature
`def tile(df: pd.DataFrame, column: str, n_tiles: int, method: str = "equal_records", output_column: str = "Tile") -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **column** | **str** | **Required** | **None**
  * **Description**: Numeric column to calculate tiles on.
* **n_tiles** | **int** | **Required** | **None**
  * **Description**: Number of tiles (bins) to generate.
* **method** | **str** | **Optional** | **"equal_records"**
  * **Description**: Strategy for binning. `"equal_records"` uses quantiles (qcut), `"equal_range"` uses equal width bins (cut).
* **output_column** | **str** | **Optional** | **"Tile"**
  * **Description**: Name of the resulting tile column.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: DataFrame with the new Tile assignment column appended.

### Exceptions & Errors
* `ValueError`: Raised if an unknown method is supplied.

### Behavior & Edge Cases
Ties at quantile edges are handled by pandas natively. Output values are 1-indexed integers representing the tile number.

### Usage Examples
1. **Basic Usage**:
   ```python
   df = Preparation.tile(df, "Age", 2)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   df = Preparation.tile(df, "Value", 2, method="equal_range")
   ```

---

## Function: `imputation`
**Description**: Replaces missing values with statistical aggregates or custom values.

### Signature
`def imputation(df: pd.DataFrame, columns: str | Sequence[str], method: str = "mean", replacement_value: Any | None = None, add_indicator: bool = True) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **columns** | **str | Sequence[str]** | **Required** | **None**
  * **Description**: Target column(s) for imputation.
* **method** | **str** | **Optional** | **"mean"**
  * **Description**: Logic to apply. Valid values: `"mean"`, `"median"`, `"mode"`, `"value"`.
* **replacement_value** | **Any | None** | **Optional** | **None**
  * **Description**: Custom static value used when `method="value"`.
* **add_indicator** | **bool** | **Optional** | **True**
  * **Description**: Generates a `{col}_WasImputed` boolean column indicating changed rows.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: DataFrame with populated missing values and optional indicators.

### Exceptions & Errors
* `ValueError`: Raised if `method="value"` but no `replacement_value` is given, or if an unknown method string is used.

### Behavior & Edge Cases
If `method="mode"` and all data is missing, it cleanly yields NaN instead of failing. Multiple modes pick the first mode automatically.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Preparation.imputation(df, "Score", method="mean")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = Preparation.imputation(df, "Score", method="value", replacement_value=0)
   ```

---

## Function: `create_samples`
**Description**: Splits a single DataFrame into distinct Estimation, Validation, and Holdout dataframes.

### Signature
`def create_samples(df: pd.DataFrame, estimation_pct: float, validation_pct: float, holdout_pct: float, random_state: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **estimation_pct** | **float** | **Required** | **None**
  * **Description**: Percentage ratio (e.g., 0.5) for the estimation set.
* **validation_pct** | **float** | **Required** | **None**
  * **Description**: Percentage ratio for the validation set.
* **holdout_pct** | **float** | **Required** | **None**
  * **Description**: Percentage ratio for the holdout set.
* **random_state** | **int | None** | **Optional** | **None**
  * **Description**: Seed for repeatable shuffling.

### Returns (Outputs)
* **Type**: `tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
* **Description**: Three DataFrames representing the Estimation, Validation, and Holdout sets.

### Exceptions & Errors
* `ValueError`: Raised if the three percentages do not sum exactly to `1.0`.

### Behavior & Edge Cases
Shuffles the DataFrame then partitions the rows precisely according to the percentages.

### Usage Examples
1. **Basic Usage**:
   ```python
   est, val, hold = Preparation.create_samples(df, 0.5, 0.3, 0.2, random_state=42)
   ```

---

## Function: `date_filter`
**Description**: Filters records logically based on an inclusive date/time range.

### Signature
`def date_filter(df: pd.DataFrame, column: str, start_date: str | pd.Timestamp | None = None, end_date: str | pd.Timestamp | None = None) -> tuple[pd.DataFrame, pd.DataFrame]`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **column** | **str** | **Required** | **None**
  * **Description**: Datetime column to apply conditions on.
* **start_date** | **str | pd.Timestamp | None** | **Optional** | **None**
  * **Description**: Inclusive minimum date threshold.
* **end_date** | **str | pd.Timestamp | None** | **Optional** | **None**
  * **Description**: Inclusive maximum date threshold.

### Returns (Outputs)
* **Type**: `tuple[pd.DataFrame, pd.DataFrame]`
* **Description**: `(true_df, false_df)` indicating rows inside and outside the boundaries.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Properly handles string inputs by parsing them natively into pandas datetimes before comparing.

### Usage Examples
1. **Basic Usage**:
   ```python
   t, f = Preparation.date_filter(df, "Date", start_date="2023-03-01", end_date="2023-06-01")
   ```

---

## Function: `oversample_field`
**Description**: Balances datasets by artificially duplicating a minority class to hit a target ratio.

### Signature
`def oversample_field(df: pd.DataFrame, column: str, value: Any, target_pct: float = 0.5, random_state: int | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **column** | **str** | **Required** | **None**
  * **Description**: Column representing the classification target.
* **value** | **Any** | **Required** | **None**
  * **Description**: The specific class value to artificially duplicate.
* **target_pct** | **float** | **Optional** | **0.5**
  * **Description**: Target fraction (0.0 to 1.0) of the final DataFrame the class should occupy.
* **random_state** | **int | None** | **Optional** | **None**
  * **Description**: Seed for deterministic duplication.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Enlarged DataFrame with the target class duplicated appropriately.

### Exceptions & Errors
* `ValueError`: Raised if `target_pct` is not strictly between 0.0 and 1.0.

### Behavior & Edge Cases
Determines how many duplicates are required to mathematically reach the target fraction compared to the background classes, then samples with replacement.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Preparation.oversample_field(df, "Class", "A", target_pct=0.5, random_state=42)
   ```

---

## Function: `rank`
**Description**: Generates rankings for values within a column, optionally partitioned by groups.

### Signature
`def rank(df: pd.DataFrame, column: str, group_by: str | Sequence[str] | None = None, ascending: bool = False, method: str = "min", output_column: str = "Rank") -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **column** | **str** | **Required** | **None**
  * **Description**: Numeric column to rank.
* **group_by** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Evaluates ranks independently within partitions.
* **ascending** | **bool** | **Optional** | **False**
  * **Description**: Sort order for ranking. If false, largest value is #1.
* **method** | **str** | **Optional** | **"min"**
  * **Description**: How to handle ties (`'min'`, `'dense'`, `'first'`, `'average'`, `'max'`).
* **output_column** | **str** | **Optional** | **"Rank"**
  * **Description**: Name of the appended rank column.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: DataFrame with the ranking column added.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Delegates directly to pandas `rank()`. Empty groups or nulls inherit standard pandas ranking constraints (usually NaN for missing data).

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Preparation.rank(df, "Score", ascending=False)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = Preparation.rank(df, "Score", group_by="Group", ascending=False)
   ```
