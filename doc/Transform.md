# Transform Overview
Provides data aggregation, reshaping (pivoting/unpivoting), and advanced mathematical tools, mirroring the visual ETL tool Transform palette.

---

## Function: `summarize`
**Description**: Groups data and executes diverse scalar aggregation functions.

### Signature
`def summarize(df: pd.DataFrame, group_by: str | Sequence[str] | None = None, aggregations: dict[str, str | list[str]] | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input dataset.
* **group_by** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Partitioning columns. If None, reduces the entire DataFrame to 1 row.
* **aggregations** | **dict[str, str | list[str]] | None** | **Optional** | **None**
  * **Description**: Mapping targeting columns to agg operations. Ex: `{"Revenue": "sum"}`.
  * **Valid Input Range/Format**: Standard stats (`"sum"`, `"mean"`, `"count"`, `"min"`, `"max"`, `"first"`, `"last"`, `"std"`, `"median"`) plus custom logic (`"count distinct"`, `"count null"`, `"count blank"`, `"count non blank"`, `"concatenate"`, `"concatenate distinct"`, `"longest"`, `"shortest"`, `"mode"`).

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Strongly-typed rolled-up dataset with auto-generated headers (e.g. `Sum_Revenue`).

### Exceptions & Errors
* `ValueError`: Raised if `aggregations` dictionary is not provided.

### Behavior & Edge Cases
Handles complex custom visual ETL tool aggs seamlessly behind the scenes. Blank string counting works reliably alongside standard NaN counting.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Transform.summarize(df, group_by="Region", aggregations={"Revenue": "sum"})
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = Transform.summarize(df, aggregations={"Val": ["longest", "shortest", "mode", "concatenate"]})
   ```

---

## Function: `transpose`
**Description**: Flattens wide columnar variables into long Key-Value row format.

### Signature
`def transpose(df: pd.DataFrame, key_columns: str | Sequence[str], data_columns: str | Sequence[str] | None = None, var_name: str = "Name", value_name: str = "Value") -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input wide DataFrame.
* **key_columns** | **str | Sequence[str]** | **Required** | **None**
  * **Description**: Identity columns to lock and repeat across unpivoted rows.
* **data_columns** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Explicit variables to unpivot. If None, grabs everything not in `key_columns`.
* **var_name** | **str** | **Optional** | **"Name"**
  * **Description**: Title for new categorical dimension column.
* **value_name** | **str** | **Optional** | **"Value"**
  * **Description**: Title for metric value column.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Melted, longer DataFrame.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Defaults to safely pulling all non-key columns if `data_columns` is omitted. Generates dense data.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Transform.transpose(df, key_columns="ID", data_columns=["Q1", "Q2"])
   ```

---

## Function: `cross_tab`
**Description**: Pivots long categorical values into distinctive horizontal columns.

### Signature
`def cross_tab(df: pd.DataFrame, group_by: str | Sequence[str], pivot_col: str, value_col: str, agg: str = "sum") -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input long DataFrame.
* **group_by** | **str | Sequence[str]** | **Required** | **None**
  * **Description**: Identifiers to define unique horizontal rows.
* **pivot_col** | **str** | **Required** | **None**
  * **Description**: The column containing category strings that will become new headers.
* **value_col** | **str** | **Required** | **None**
  * **Description**: The column housing the numeric data to spread out.
* **agg** | **str** | **Optional** | **"sum"**
  * **Description**: Resolution strategy if multiple rows share the same `group_by` and `pivot_col` intersection.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Widened DataFrame with categories extracted to header namespace.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Aggregates implicit duplicates smoothly based on the `agg` logic.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Transform.cross_tab(df, group_by="Region", pivot_col="Quarter", value_col="Revenue")
   ```

---

## Function: `running_total`
**Description**: Computes a cumulative sequential sum down a numeric column.

### Signature
`def running_total(df: pd.DataFrame, column: str, group_by: str | Sequence[str] | None = None, output_column: str | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **column** | **str** | **Required** | **None**
  * **Description**: Numeric column to accumulate.
* **group_by** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Isolated partition boundaries. Totals reset to zero at new group borders.
* **output_column** | **str | None** | **Optional** | **None**
  * **Description**: Column name. Defaults to `"RunningTotal_{column}"`.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: DataFrame with the cumulative column appended.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Operates securely over grouped boundaries using pandas cumulative aggregations without leaking across groups.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Transform.running_total(df, "Value")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = Transform.running_total(df, "Revenue", group_by="Region")
   ```

---

## Function: `count_records`
**Description**: Analyzes overall length of data stream.

### Signature
`def count_records(df: pd.DataFrame, output_col: str = "Count") -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **output_col** | **str** | **Optional** | **"Count"**
  * **Description**: The returned column title.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A 1-by-1 DataFrame holding the integer length.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Guarantees a scalar 1-row return value regardless of whether the incoming df is empty or large.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Transform.count_records(df)
   ```

---

## Function: `arrange`
**Description**: Simultaneously transposes complex blocks of columns back into standardized aligned structures.

### Signature
`def arrange(df: pd.DataFrame, key_columns: str | Sequence[str] | None = None, output_mapping: dict[str, Sequence[str]] | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **key_columns** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Shared identifier tags for the new rows.
* **output_mapping** | **dict[str, Sequence[str]] | None** | **Optional** | **None**
  * **Description**: Dictionary connecting newly minted header names to ordered lists of original messy column names.
  * **Valid Input Range/Format**: E.g., `{"Sales": ["Q1_Sales", "Q2_Sales"]}`. Arrays inside dict must be perfectly identical in length.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Structurally normalized DataFrame.

### Exceptions & Errors
* `ValueError`: Raised if mapping lists are unequal lengths.

### Behavior & Edge Cases
Acts as a multi-variable melt algorithm, stacking data while keeping multiple distinct value dimensions grouped coherently.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Transform.arrange(
       df, key_columns="ID", output_mapping={"Sales": ["Q1_S", "Q2_S"], "Costs": ["Q1_C", "Q2_C"]}
   )
   ```

---

## Function: `make_columns`
**Description**: Wraps sequential row data into horizontal multi-column bundles, flattening the dataset vertically.

### Signature
`def make_columns(df: pd.DataFrame, num_columns: int) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Tall input DataFrame.
* **num_columns** | **int** | **Required** | **None**
  * **Description**: Targeted width multiplier.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Shorter DataFrame with suffixed wrapped columns (`Val_1`, `Val_2`).

### Exceptions & Errors
* `ValueError`: Raised if `num_columns` is < 1.

### Behavior & Edge Cases
Pads trailing empty cells with NaN if the original row count is not perfectly divisible by the divisor.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Transform.make_columns(df, num_columns=3)
   ```

---

## Function: `weighted_average`
**Description**: Statistically corrects metric averages by weighing them against an external significance column.

### Signature
`def weighted_average(df: pd.DataFrame, value_column: str, weight_column: str, group_by: str | Sequence[str] | None = None, output_column: str = "WeightedAverage") -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input DataFrame.
* **value_column** | **str** | **Required** | **None**
  * **Description**: Scalar measurements.
* **weight_column** | **str** | **Required** | **None**
  * **Description**: Gravitational / statistical influence values.
* **group_by** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Executes mathematically isolated calculations per group partition.
* **output_column** | **str** | **Optional** | **"WeightedAverage"**
  * **Description**: Resultant value header.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: DataFrame with the calculated float values.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Handles groups naturally. Evaluates standard sumproduct division algorithms safely.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Transform.weighted_average(df, "Val", "Weight", group_by="Grp")
   ```
