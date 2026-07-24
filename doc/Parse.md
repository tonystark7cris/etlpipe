# Parse Overview
Translates strings via complex regular expressions, splits tokens, dissects XML trees, and converts datetime objects, mirroring the visual ETL tool Parse tool palette.

---

## Function: `date_time`
**Description**: Casts string timestamps into standard datetimes, or alters output string layouts.

### Signature
`def date_time(df: pd.DataFrame, column: str, input_fmt: str | None = None, output_fmt: str | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input data stream.
* **column** | **str** | **Required** | **None**
  * **Description**: Source time string column.
* **input_fmt** | **str | None** | **Optional** | **None**
  * **Description**: Optional `strftime` string defining current shape. If None, delegates to pandas parsing inference.
* **output_fmt** | **str | None** | **Optional** | **None**
  * **Description**: Optional string formatting layout. If None, leaves underlying type as native `datetime64`.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Dataframe with parsed temporal values replacing the raw text.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Autodetection resolves standard ISO dates effectively.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Parse.date_time(df, "D")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = Parse.date_time(df, "DateStr", input_fmt="%m/%d/%Y", output_fmt="%Y-%m-%d")
   ```

---

## Function: `regex_match`
**Description**: Applies a Regex search against rows to isolate conforming strings into boolean masks.

### Signature
`def regex_match(df: pd.DataFrame, column: str, pattern: str, output_column: str = "Match") -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Dataset.
* **column** | **str** | **Required** | **None**
  * **Description**: Text dimension.
* **pattern** | **str** | **Required** | **None**
  * **Description**: Regular expression search criteria.
* **output_column** | **str** | **Optional** | **"Match"**
  * **Description**: Output header mapping to the boolean logic flags.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Dataframe with the boolean match column trailing the end.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Matches evaluate via `re.match` equivalent behavior (standard Python regex syntax).

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Parse.regex_match(df, "Email", r"^[\w.]+@[\w.]+$")
   ```

---

## Function: `regex_parse`
**Description**: Dissects targeted strings based on regex capturing groups and lifts the captured strings into brand new columns.

### Signature
`def regex_parse(df: pd.DataFrame, column: str, pattern: str, output_cols: Sequence[str] | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Input df.
* **column** | **str** | **Required** | **None**
  * **Description**: String field to operate on.
* **pattern** | **str** | **Required** | **None**
  * **Description**: Regex pattern possessing capturing parenthesis blocks (e.g. `(\w+)`).
* **output_cols** | **Sequence[str] | None** | **Optional** | **None**
  * **Description**: Mapped identities for extracted columns. If None, populates as `Group_1`, `Group_2`.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Expanded DataFrame carrying the newly captured categorical dimensions.

### Exceptions & Errors
* `ValueError`: Raised if the volume of strings provided in `output_cols` diverges from the count of capture blocks detected inside `pattern`.

### Behavior & Edge Cases
Auto-names captures robustly if headers are entirely missing. Non-matching rows generate None/NaNs in the new columns.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Parse.regex_parse(df, "FullName", r"(\w+)\s+(\w+)", output_cols=["First", "Last"])
   ```

---

## Function: `regex_replace`
**Description**: Eradicates or manipulates characters inside strings via RegEx matching.

### Signature
`def regex_replace(df: pd.DataFrame, column: str, pattern: str, replacement: str) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Source table.
* **column** | **str** | **Required** | **None**
  * **Description**: Column header.
* **pattern** | **str** | **Required** | **None**
  * **Description**: Destructive regex pattern logic.
* **replacement** | **str** | **Required** | **None**
  * **Description**: String data substituting matched zones. Understands regex backtracking refs (`\1`).

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: DataFrame with the target column cleansed and altered.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Matches anywhere inside the target string (pandas `str.replace` logic, applying `regex=True`).

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Parse.regex_replace(df, "Phone", r"\D", "")
   ```

---

## Function: `regex_tokenize`
**Description**: Splits dense lists or text strings along Regex boundaries either vertically (row fan-out) or horizontally (column fan-out).

### Signature
`def regex_tokenize(df: pd.DataFrame, column: str, pattern: str, split_to: str = "rows") -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Table.
* **column** | **str** | **Required** | **None**
  * **Description**: Encapsulated field.
* **pattern** | **str** | **Required** | **None**
  * **Description**: Regular expression token delimiter.
* **split_to** | **str** | **Optional** | **"rows"**
  * **Description**: Orientation argument (`"rows"` generates row duplication; `"columns"` spreads fields side-to-side).

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Exploded DataFrame (either vertically longer or horizontally wider).

### Exceptions & Errors
* `ValueError`: Raised if `split_to` string is invalid.

### Behavior & Edge Cases
Dynamically handles variable counts of splits per row when fanning out vertically, preserving other column properties.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Parse.regex_tokenize(df, "Tags", r",\s*", split_to="rows")
   ```

---

## Function: `text_to_columns`
**Description**: Straightforward flat literal delimiter text split (differs from tokenizing by utilizing standard characters rather than regex interpretation).

### Signature
`def text_to_columns(df: pd.DataFrame, column: str, delimiter: str, split_to: str = "columns", num_columns: int | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Dataframe object.
* **column** | **str** | **Required** | **None**
  * **Description**: Delimited field.
* **delimiter** | **str** | **Required** | **None**
  * **Description**: Static separation string (e.g., `|`, `,`).
* **split_to** | **str** | **Optional** | **"columns"**
  * **Description**: Layout flag (`"columns"` or `"rows"`).
* **num_columns** | **int | None** | **Optional** | **None**
  * **Description**: Soft limits maximum width of expansion if `split_to="columns"`.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Modified table featuring split substrings.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Safely coerces missing boundaries or excessive boundaries dynamically.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Parse.text_to_columns(df, "Skills", "|", split_to="columns")
   ```

---

## Function: `xml_parse`
**Description**: Queries HTML/XML markup blobs efficiently leveraging robust XPath queries.

### Signature
`def xml_parse(df: pd.DataFrame, column: str, xpath: str, output_column: str = "ParsedXML", return_child_values: bool = False, return_outer_xml: bool = False) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: Text dataframe.
* **column** | **str** | **Required** | **None**
  * **Description**: Column holding `<xml>` text shapes.
* **xpath** | **str** | **Required** | **None**
  * **Description**: Locational query logic (e.g. `.//person`).
* **output_column** | **str** | **Optional** | **"ParsedXML"**
  * **Description**: Prefix / standard title for output components.
* **return_child_values** | **bool** | **Optional** | **False**
  * **Description**: Expands children arrays inside the node out into independent distinct dataframe columns.
* **return_outer_xml** | **bool** | **Optional** | **False**
  * **Description**: Preserves exact tag text wrapping extracted data points.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: Flattened tabular view based on internal parsed nodes.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Silently yields None/NaN if XPath trajectories fail or evaluate into nothing, protecting the pipeline from exceptions.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = Parse.xml_parse(df, "XML", ".//name", "Name")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = Parse.xml_parse(df, "XML", ".//person", "Person", return_child_values=True)
   ```
