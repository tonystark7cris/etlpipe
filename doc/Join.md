# Join Overview
Handles joining, uniting, and string-matching logic across multiple data streams, mirroring the visual ETL tool Join tool palette.

---

## Function: `join`
**Description**: Merges two DataFrames on a specified key and yields all combinations of matched and unmatched rows.

### Signature
`def join(left: pd.DataFrame, right: pd.DataFrame, on: str | Sequence[str] | None = None, left_on: str | Sequence[str] | None = None, right_on: str | Sequence[str] | None = None, suffixes: tuple[str, str] = ("_left", "_right")) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`

### Parameters (Inputs)
* **left** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Left-side DataFrame.
* **right** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Right-side DataFrame.
* **on** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Shared column name(s) to join on.
* **left_on** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Left-specific join column(s).
* **right_on** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Right-specific join column(s).
* **suffixes** | **tuple[str, str]** | **Optional** | **("_left", "_right")**
  * **Description**: Suffixes to resolve overlapping column names during join.

### Returns (Outputs)
* **Type**: `tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
* **Description**: `(L, J, R)` tuple matching visual ETL tool anchors. `L` is left-unjoined, `J` is joined (inner), `R` is right-unjoined.

### Exceptions & Errors
None explicitly defined (delegates to pandas).

### Behavior & Edge Cases
Handles datatype drifts efficiently (e.g., comparing string "1" to integer 1 resolves as a valid match under the hood). If `on`, `left_on`, and `right_on` are missing, assumes common columns or relies on index joining depending on engine implementation.

### Usage Examples
1. **Basic Usage**:
   ```python
   L, J, R = Join.join(df1, df2, on="CustomerID")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   L, J, R = Join.join(df1, df2, left_on="ID_A", right_on="ID_B")
   ```

---

## Function: `join_multiple`
**Description**: Aggregates three or more DataFrames along common keys in a single operation.

### Signature
`def join_multiple(*dfs: pd.DataFrame, on: str | Sequence[str] | None = None, join_type: str = "outer") -> pd.DataFrame`

### Parameters (Inputs)
* **dfs** | **pd.DataFrame (Variable)** | **Required** | **None**
  * **Description**: Multiple DataFrames supplied as positional arguments.
* **on** | **str | Sequence[str] | None** | **Optional** | **None**
  * **Description**: Column(s) shared in *all* DataFrames. If None, joins on common columns implicitly.
* **join_type** | **str** | **Optional** | **"outer"**
  * **Description**: `inner` or `outer` merge behavior.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A single consolidated DataFrame.

### Exceptions & Errors
* `ValueError`: Raised if fewer than two DataFrames are passed.

### Behavior & Edge Cases
Outer joins will populate NaNs in missing regions. Resolves overlapping column suffixes automatically across arbitrarily many inputs.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Join.join_multiple(df1, df2, df3, on="ID")
   ```

---

## Function: `union`
**Description**: Stacks multiple DataFrames vertically on top of one another.

### Signature
`def union(*dfs: pd.DataFrame, by: str = "name") -> pd.DataFrame`

### Parameters (Inputs)
* **dfs** | **pd.DataFrame (Variable)** | **Required** | **None**
  * **Description**: Multiple DataFrames supplied positionally.
* **by** | **str** | **Optional** | **"name"**
  * **Description**: Configuration string deciding stacking alignment. `"name"` stacks columns sharing the exact same string header; `"position"` ignores header strings and stacks by ordinal column index.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Concatenated DataFrame.

### Exceptions & Errors
* `ValueError`: Raised if fewer than two DataFrames are provided.

### Behavior & Edge Cases
Missing headers in "name" alignment get filled with NaNs for unaligned rows. Position alignment forces data together regardless of semantic meaning, which is powerful but dangerous.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Join.union(df1, df2)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = Join.union(df1, df2, by="position")
   ```

---

## Function: `find_replace`
**Description**: Locates specific tokens in a primary DataFrame and replaces or appends based on a lookup dictionary DataFrame.

### Signature
`def find_replace(df: pd.DataFrame, find_df: pd.DataFrame, find_col: str, replace_col: str, target_col: str | None = None, mode: str = "entire", append: bool = False) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Main body of data.
* **find_df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Lookup configuration dataset.
* **find_col** | **str** | **Required** | **None**
  * **Description**: Column in `find_df` with search queries.
* **replace_col** | **str** | **Required** | **None**
  * **Description**: Column in `find_df` with replacement strings.
* **target_col** | **str | None** | **Optional** | **None**
  * **Description**: Column in `df` to scan. If None, targets `find_col` name.
* **mode** | **str** | **Optional** | **"entire"**
  * **Description**: `"entire"` requires an exact string match; `"partial"` searches for substrings.
* **append** | **bool** | **Optional** | **False**
  * **Description**: If True, adds a new column instead of overwriting `target_col`.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Modified DataFrame with translated text strings.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Partial matches sequentially apply rules. Unmatched targets remain entirely unmodified (or receive NaN if `append=True`).

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Join.find_replace(df, mapping_df, "StateCode", "StateName")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = Join.find_replace(df, mapping, "Find", "Category", target_col="Text", mode="partial", append=True)
   ```

---

## Function: `make_group`
**Description**: Identifies networks/islands of related pairs and groups them into connected components.

### Signature
`def make_group(df: pd.DataFrame, key1: str, key2: str) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input dataset modeling relationships.
* **key1** | **str** | **Required** | **None**
  * **Description**: Left-side node of edge.
* **key2** | **str** | **Required** | **None**
  * **Description**: Right-side node of edge.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Two-column DataFrame (`Group`, `Key`) defining component membership.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Evaluates transitive links. E.g., A=B and B=C yields Group A containing A, B, C. Null targets map back to isolated nodes.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Join.make_group(df, "Key1", "Key2")
   ```

---

## Function: `append_fields`
**Description**: Evaluates a Cartesian (cross) product connecting every row on the left to every row on the right.

### Signature
`def append_fields(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame`

### Parameters (Inputs)
* **left** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Base DataFrame.
* **right** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Permutation DataFrame.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Highly expanded DataFrame encompassing all valid combinations (N x M rows).

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
No joining keys required. Expands geometrically. Overlapping columns receive suffixes naturally via pandas logic.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Join.append_fields(df1, df2)
   ```

---

## Function: `fuzzy_match`
**Description**: Applies sequence matching heuristics to discover structurally similar strings across datasets.

### Signature
`def fuzzy_match(left: pd.DataFrame, right: pd.DataFrame, left_on: str, right_on: str, threshold: float = 0.6, score_column: str = "MatchScore") -> pd.DataFrame`

### Parameters (Inputs)
* **left** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Base DataFrame.
* **right** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Target DataFrame to check against.
* **left_on** | **str** | **Required** | **None**
  * **Description**: Key in left.
* **right_on** | **str** | **Required** | **None**
  * **Description**: Key in right.
* **threshold** | **float** | **Optional** | **0.6**
  * **Description**: Minimum SequenceMatcher ratio (0.0 to 1.0) necessary to declare a match.
* **score_column** | **str** | **Optional** | **"MatchScore"**
  * **Description**: Appended column holding the raw float similarity metric.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Matched intersection pairs along with their metric score.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Filters out pairs below the threshold. If no matches pass threshold (e.g. 0.99), returns an empty dataframe with correct schema.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Join.fuzzy_match(df1, df2, "Company", "Name", threshold=0.5)
   ```
