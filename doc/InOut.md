# InOut Overview
Handles reading, writing, browsing, and generating data from external sources, mirroring the visual ETL tool In/Out tool palette.

---

## Function: `input_data`
**Description**: Reads data from a file into a DataFrame, auto-detecting the file format from the extension.

### Signature
`def input_data(path: str | Path, **kwargs: Any) -> pd.DataFrame`

### Parameters (Inputs)
* **path** | **str | Path** | **Required** | **None**
  * **Description**: Path to the data file.
  * **Valid Input Range/Format**: A valid file path pointing to a supported extension (e.g., `.csv`, `.json`, `.xlsx`).
* **kwargs** | **Any** | **Optional** | **None**
  * **Description**: Extra keyword arguments forwarded to the underlying pandas reader function.
  * **Valid Input Range/Format**: Any valid pandas read function arguments (e.g., `sheet_name="Q1"` for Excel).

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A new DataFrame containing the file contents.

### Exceptions & Errors
* `FileNotFoundError`: Raised if the specified file does not exist.
* `ValueError`: Raised if the file extension is not supported by the underlying pandas readers.
* `DeprecationWarning`: Raised if attempting to read a `.pkl` or `.pickle` file due to arbitrary code execution risks.

### Behavior & Edge Cases
The function determines the correct pandas reading method based on the file extension (`.csv` -> `read_csv`, etc.). If a pickle file is loaded, it triggers a warning but still loads the data.

### Usage Examples
1. **Basic Usage**:
   ```python
   df = InOut.input_data("data.csv")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   df = InOut.input_data("report.xlsx", sheet_name="Q1")
   ```

---

## Function: `output_data`
**Description**: Writes a DataFrame to a file, inferring the correct format based on the given file extension.

### Signature
`def output_data(df: pd.DataFrame, path: str | Path, **kwargs: Any) -> None`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: The DataFrame to write to a file.
  * **Valid Input Range/Format**: Must be a valid pandas DataFrame object.
* **path** | **str | Path** | **Required** | **None**
  * **Description**: Destination file path.
  * **Valid Input Range/Format**: A valid file path with a supported extension (e.g., `.csv`, `.parquet`).
* **kwargs** | **Any** | **Optional** | **None**
  * **Description**: Extra keyword arguments forwarded to the underlying pandas writer method.
  * **Valid Input Range/Format**: Any valid pandas to_ function arguments (e.g., `index=False`).

### Returns (Outputs)
* **Type**: `None`
* **Description**: This function does not return anything. It writes data to the filesystem.

### Exceptions & Errors
* `TypeError`: Raised if `df` is not a pandas DataFrame object.
* `ValueError`: Raised if the file extension is not supported.
* `DeprecationWarning`: Raised if writing to `.pkl` or `.pickle`.

### Behavior & Edge Cases
Automatically creates parent directories if they don't exist. Warns about pickle serialization deprecation. Uses engine abstractions to write the file.

### Usage Examples
1. **Basic Usage**:
   ```python
   InOut.output_data(df, "output.csv")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   InOut.output_data(df, "output.parquet", index=False)
   ```

---

## Function: `text_input`
**Description**: Creates a DataFrame from inline data structures like dictionaries or lists of records.

### Signature
`def text_input(data: dict[str, list] | list[dict] | list[list | tuple], columns: Sequence[str] | None = None) -> pd.DataFrame`

### Parameters (Inputs)
* **data** | **dict[str, list] | list[dict] | list[list | tuple]** | **Required** | **None**
  * **Description**: Data supplied either as a column-oriented dictionary, row-oriented list of dicts, or a list of rows.
  * **Valid Input Range/Format**: Properly formatted structured data collections.
* **columns** | **Sequence[str] | None** | **Optional** | **None**
  * **Description**: Column names to apply when `data` is a list of lists or tuples.
  * **Valid Input Range/Format**: Sequence of strings matching the length of the data rows.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A new DataFrame instantiated from the provided data.

### Exceptions & Errors
* `ValueError`: Raised if `data` is a list of lists/tuples and `columns` is not provided.

### Behavior & Edge Cases
Automatically infers data types based on the passed Python objects. If rows are missing keys in `list[dict]` format, pandas fills them with NaNs.

### Usage Examples
1. **Basic Usage**:
   ```python
   df = InOut.text_input({"Name": ["Alice", "Bob"], "Age": [30, 25]})
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   df = InOut.text_input([[1, 2], [3, 4]], columns=["X", "Y"])
   ```

---

## Function: `browse`
**Description**: Displays summary information about a DataFrame to standard output and returns it unchanged for pipeline chaining.

### Signature
`def browse(df: pd.DataFrame, n: int = 10) -> pd.DataFrame`

### Parameters (Inputs)
* **df** | **pd.DataFrame** | **Required** | **None**
  * **Description**: The DataFrame to inspect.
  * **Valid Input Range/Format**: Any valid pandas DataFrame.
* **n** | **int** | **Optional** | **10**
  * **Description**: Number of head rows to display.
  * **Valid Input Range/Format**: Non-negative integer.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: The exact same `df` instance (unmodified).

### Exceptions & Errors
* `TypeError`: Raised if `df` is not a DataFrame.

### Behavior & Edge Cases
Prints shape, types, null counts, stats, and the first `n` rows. Does not mutate the DataFrame in any way.

### Usage Examples
1. **Basic Usage**:
   ```python
   result = InOut.browse(df)
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   result = InOut.browse(df, n=3)
   ```

---

## Function: `directory`
**Description**: Lists files in a directory that match a specific glob pattern, returning a DataFrame with file metadata.

### Signature
`def directory(path: str | Path, pattern: str = "*") -> pd.DataFrame`

### Parameters (Inputs)
* **path** | **str | Path** | **Required** | **None**
  * **Description**: Directory path to scan.
  * **Valid Input Range/Format**: A string or Path object pointing to an existing directory.
* **pattern** | **str** | **Optional** | **"*"**
  * **Description**: A glob pattern to filter files.
  * **Valid Input Range/Format**: A standard shell glob pattern string (e.g., `*.csv`).

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A DataFrame containing file metadata including `FullPath`, `Directory`, `FileName`, `ShortFileName`, `CreationTime`, `LastWriteTime`, `LastAccessTime`, and `Size`.

### Exceptions & Errors
* `FileNotFoundError`: Raised if the `path` does not exist or is not a directory.

### Behavior & Edge Cases
Empty directories return an empty DataFrame with the correct schema.

### Usage Examples
1. **Basic Usage**:
   ```python
   files_df = InOut.directory("./data")
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   csv_files = InOut.directory("./data", "*.csv")
   ```

---

## Function: `date_time_now`
**Description**: Returns the current date and time as a single-row DataFrame.

### Signature
`def date_time_now() -> pd.DataFrame`

### Parameters (Inputs)
None.

### Returns (Outputs)
* **Type**: `pd.DataFrame`
* **Description**: A DataFrame containing one row and one column named `DateTime` populated with the current timestamp.

### Exceptions & Errors
None explicitly defined.

### Behavior & Edge Cases
Always returns a single-element DataFrame. The time is based on the local system's clock.

### Usage Examples
1. **Basic Usage**:
   ```python
   now_df = InOut.date_time_now()
   ```
2. **Advanced Usage/Edge Cases**:
   ```python
   # Typically joined or appended for timestamps
   timestamped_df = df.assign(RunTime=InOut.date_time_now()["DateTime"].iloc[0])
   ```
