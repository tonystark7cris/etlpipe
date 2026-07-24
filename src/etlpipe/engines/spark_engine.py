"""PySpark backend engine implementation for etlpipe.

Executes operations using native Spark SQL, Vectorized Pandas UDFs,
or Driver-side fallbacks based on the 3-Tier execution strategy.
"""

from __future__ import annotations

import difflib
import json
import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from functools import reduce
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import pyspark.sql.functions as F
    from pyspark.sql import DataFrame as SparkDataFrame
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import pandas_udf
    from pyspark.sql.types import ByteType, DoubleType, IntegerType, LongType, ShortType, StringType
    from pyspark.sql.window import Window
except ImportError:
    # We allow importing this module so get_engine() can raise a clean error
    SparkSession = None
    SparkDataFrame = None
    F = None
    Window = None
    pandas_udf = None
    StringType = LongType = IntegerType = ShortType = ByteType = DoubleType = type(None)


from etlpipe.engines.base import BackendEngine

logger = logging.getLogger("etlpipe.engines.spark")


class SparkEngine(BackendEngine):
    """Concrete backend engine executing operations on PySpark."""

    def __init__(
        self,
        spark: Any = None,
        broadcast_threshold: int = 10 * 1024 * 1024,
        max_collect_bytes: int = 200 * 1024 * 1024,
        checkpoint_interval: int = 10,
    ):
        if SparkSession is None:
            raise ImportError(
                "PySpark is required for the Spark backend. Install it with: pip install etlpipe[spark]"
            )

        if spark is None:
            self.spark = SparkSession.builder.getOrCreate()
        else:
            self.spark = spark

        self.broadcast_threshold = broadcast_threshold
        self.max_collect_bytes = max_collect_bytes
        self.checkpoint_interval = checkpoint_interval

        # State tracking for auto-checkpointing
        self._step_counter = 0

    @property
    def name(self) -> str:
        return "spark"

    def _log_operation(
        self, method: str, input_df: SparkDataFrame | None = None, output_df: SparkDataFrame | None = None
    ) -> SparkDataFrame | None:
        """Log enterprise telemetry and apply auto-checkpointing."""
        self._step_counter += 1

        log_data = {
            "backend": "spark",
            "tool": method,
            "timestamp": datetime.now().isoformat(),
            "step": self._step_counter,
        }

        # We don't log exact row counts for Spark by default because .count() triggers a job,
        # which defeats lazy execution. We log the action intent.
        if input_df is not None:
            log_data["input_schema_hash"] = hash(str(input_df.schema))

        # Auto-checkpointing logic
        if (
            output_df is not None
            and self.checkpoint_interval > 0
            and self._step_counter % self.checkpoint_interval == 0
        ):
            logger.info(f"Auto-checkpointing at step {self._step_counter} for {method}")
            # Ensure checkpoint dir is set in SparkSession before calling this
            try:
                output_df = output_df.checkpoint(eager=False)
                log_data["checkpointed"] = True
            except Exception as e:
                logger.warning(f"Failed to auto-checkpoint: {e}")

        logger.debug(json.dumps(log_data))
        return output_df

    def _estimate_df_size(self, df: SparkDataFrame) -> int:
        """Estimate the size in bytes of a SparkDataFrame before collecting."""
        # A rough heuristic: count rows and multiply by avg row size based on schema
        try:
            row_count = df.count()
            avg_row_bytes = len(df.columns) * 8  # assuming 8 bytes per cell on avg
            return row_count * avg_row_bytes
        except Exception:
            return self.max_collect_bytes + 1  # Assume it's too big if we can't estimate

    def _safe_collect(self, df: SparkDataFrame, operation_name: str) -> pd.DataFrame:
        """Collect to Pandas with driver-memory size protection (Tier 3 fallback)."""
        estimated = self._estimate_df_size(df)
        if estimated > self.max_collect_bytes:
            raise MemoryError(
                f"[{operation_name}] etlpipeMemoryError: Estimated collection size "
                f"(~{estimated // 1024**2} MB) exceeds maximum threshold "
                f"({self.max_collect_bytes // 1024**2} MB). "
                f"Consider filtering data before this operation or increasing max_collect_bytes."
            )
        return df.toPandas()

    @staticmethod
    def _pandas_dtype_to_spark_type(dtype) -> str:
        """Map a pandas dtype to a Spark SQL type string for pandas_udf declarations."""

        dtype_str = str(dtype)
        if "int" in dtype_str:
            return "long"
        elif "float" in dtype_str:
            return "double"
        elif "bool" in dtype_str:
            return "boolean"
        elif "datetime" in dtype_str:
            return "timestamp"
        else:
            return "string"

    # ================================================================== #
    #  Preparation Palette
    # ================================================================== #

    def filter(
        self,
        df: SparkDataFrame,
        condition: str | Callable | None = None,
        *,
        column: str | None = None,
        operator: str | None = None,
        value: Any = None,
    ) -> tuple[SparkDataFrame, SparkDataFrame]:

        if condition is not None:
            if callable(condition):
                # Tier 2: Vectorized UDF
                schema = df.schema

                @pandas_udf("boolean")
                def apply_condition(*cols: pd.Series) -> pd.Series:
                    pdf = pd.DataFrame({c.name: s for c, s in zip(schema, cols, strict=False)})
                    return condition(pdf)

                cond_col = apply_condition(*[F.col(c) for c in df.columns])
                true_df = df.filter(cond_col)
                false_df = df.filter(~cond_col)
            else:
                # Tier 1: Native expr
                true_df = df.filter(F.expr(condition))
                false_df = df.filter(~F.expr(condition))
        elif column is not None and operator is not None:
            col = F.col(column)
            op = operator.lower().strip()
            if op in ("=", "==", "equals"):
                mask_expr = col == value
            elif op in ("!=", "does not equal"):
                mask_expr = col != value
            elif op == ">":
                mask_expr = col > value
            elif op == ">=":
                mask_expr = col >= value
            elif op == "<":
                mask_expr = col < value
            elif op == "<=":
                mask_expr = col <= value
            elif op == "is null":
                mask_expr = col.isNull()
            elif op == "is not null":
                mask_expr = col.isNotNull()
            elif op == "is empty":
                mask_expr = col.isNull() | (col == "")
            elif op == "is not empty":
                mask_expr = col.isNotNull() & (col != "")
            elif op == "contains":
                mask_expr = col.contains(str(value))
            elif op == "does not contain":
                mask_expr = ~col.contains(str(value))
            elif op == "is true":
                mask_expr = col == True  # noqa: E712
            elif op == "is false":
                mask_expr = col == False  # noqa: E712
            else:
                raise ValueError(f"Unsupported operator: {operator}")

            true_df = df.filter(mask_expr)
            false_df = df.filter(~mask_expr)
        else:
            raise ValueError("Must provide 'condition' or both 'column' and 'operator'.")

        true_df = self._log_operation("Preparation.filter", df, true_df)
        false_df = self._log_operation("Preparation.filter_false", df, false_df)
        return true_df, false_df

    def formula(
        self,
        df: SparkDataFrame,
        column: str,
        expression: str | Callable,
    ) -> SparkDataFrame:
        if callable(expression):
            # Tier 2: Pandas UDF with dynamic return-type inference.
            # Run the expression on a small sample to infer the output dtype,
            # then use the correct Spark type instead of hardcoding StringType.
            schema = df.schema
            sample_pdf = df.limit(2).toPandas()
            if not sample_pdf.empty:
                sample_result = expression(sample_pdf)
                spark_return_type = self._pandas_dtype_to_spark_type(sample_result.dtype)
            else:
                spark_return_type = "string"

            @pandas_udf(spark_return_type)
            def apply_expr(*cols: pd.Series) -> pd.Series:
                pdf = pd.DataFrame({c.name: s for c, s in zip(schema, cols, strict=False)})
                return expression(pdf)

            out = df.withColumn(column, apply_expr(*[F.col(c) for c in df.columns]))
        else:
            # Transpile Python/Pandas equality syntax to Spark SQL equality syntax
            if isinstance(expression, str):
                # Note: Spark SQL uses `=` for equality comparison, but blindly replacing
                # `==` with `=` is dangerous â€” it can turn boolean comparisons like
                # `A == 'value'` into assignment-like expressions in some contexts.
                # We keep `==` as-is because Spark SQL `expr()` also accepts `==`
                # for comparisons since Spark 2.x+.

                # Auto-backtick column names with spaces for safe evaluation
                for c in df.columns:
                    if " " in c and c in expression and f"`{c}`" not in expression:
                        expression = expression.replace(c, f"`{c}`")
            out = df.withColumn(column, F.expr(expression))

        return self._log_operation("Preparation.formula", df, out)

    def select(
        self,
        df: SparkDataFrame,
        columns: Sequence[str] | None = None,
        renames: dict[str, str] | None = None,
        dtypes: dict[str, str | type] | None = None,
    ) -> SparkDataFrame:
        out = df
        if columns is not None:
            out = out.select(*columns)
        if renames:
            for old, new in renames.items():
                out = out.withColumnRenamed(old, new)
        if dtypes:
            for col_name, dtype in dtypes.items():
                if dtype in (int, "int", "integer"):
                    spark_type = "int"
                elif dtype in (float, "float", "double"):
                    spark_type = "double"
                elif dtype in (str, "str", "string"):
                    spark_type = "string"
                elif dtype in (bool, "bool", "boolean"):
                    spark_type = "boolean"
                else:
                    spark_type = "string"
                out = out.withColumn(col_name, F.col(col_name).cast(spark_type))
        return self._log_operation("Preparation.select", df, out)

    def data_cleansing(
        self,
        df: SparkDataFrame,
        columns: Sequence[str] | None = None,
        remove_null_rows: bool = False,
        replace_nulls_with: Any | None = None,
        strip_whitespace: bool = True,
        remove_letters: bool = False,
        remove_numbers: bool = False,
        remove_punctuation: bool = False,
        modify_case: str | None = None,
    ) -> SparkDataFrame:
        out = df
        if columns is None:
            columns = [f.name for f in df.schema.fields if isinstance(f.dataType, StringType)]

        if remove_null_rows:
            out = out.dropna(subset=columns)

        if replace_nulls_with is not None:
            out = out.fillna({c: replace_nulls_with for c in columns})

        for col in columns:
            if strip_whitespace:
                out = out.withColumn(col, F.trim(F.col(col)))
            if remove_letters:
                out = out.withColumn(col, F.regexp_replace(col, r"[A-Za-z]", ""))
            if remove_numbers:
                out = out.withColumn(col, F.regexp_replace(col, r"\d", ""))
            if remove_punctuation:
                out = out.withColumn(col, F.regexp_replace(col, r"[^\w\s]", ""))
            if modify_case == "lower":
                out = out.withColumn(col, F.lower(F.col(col)))
            elif modify_case == "upper":
                out = out.withColumn(col, F.upper(F.col(col)))
            elif modify_case == "title":
                out = out.withColumn(col, F.initcap(F.col(col)))

        return self._log_operation("Preparation.data_cleansing", df, out)

    def sort(
        self,
        df: SparkDataFrame,
        columns: str | Sequence[str],
        ascending: bool | Sequence[bool] = True,
    ) -> SparkDataFrame:
        if isinstance(columns, str):
            columns = [columns]
        if isinstance(ascending, bool):
            ascending = [ascending] * len(columns)
        order = [F.col(c).asc() if a else F.col(c).desc() for c, a in zip(columns, ascending, strict=False)]
        out = df.orderBy(*order)
        return self._log_operation("Preparation.sort", df, out)

    def unique(
        self,
        df: SparkDataFrame,
        columns: str | Sequence[str],
        ignore_case: bool = False,
    ) -> tuple[SparkDataFrame, SparkDataFrame]:
        if isinstance(columns, str):
            columns = [columns]

        if ignore_case:
            compare_cols = [f"_fs_cmp_{c}" for c in columns]
            out = df
            for c, cc in zip(columns, compare_cols, strict=False):
                out = out.withColumn(cc, F.lower(F.col(c)))
            w = Window.partitionBy(*compare_cols).orderBy(F.monotonically_increasing_id())
            out = out.withColumn("_fs_rn", F.row_number().over(w))
            unique_df = out.filter(F.col("_fs_rn") == 1).drop("_fs_rn", *compare_cols)
            dup_df = out.filter(F.col("_fs_rn") > 1).drop("_fs_rn", *compare_cols)
        else:
            w = Window.partitionBy(*columns).orderBy(F.monotonically_increasing_id())
            out = df.withColumn("_fs_rn", F.row_number().over(w))
            unique_df = out.filter(F.col("_fs_rn") == 1).drop("_fs_rn")
            dup_df = out.filter(F.col("_fs_rn") > 1).drop("_fs_rn")

        unique_df = self._log_operation("Preparation.unique", df, unique_df)
        dup_df = self._log_operation("Preparation.unique_dups", df, dup_df)
        return unique_df, dup_df

    def sample(
        self,
        df: SparkDataFrame,
        n: int | None = None,
        pct: float | None = None,
        random: bool = False,
        position: str = "first",
        random_state: int | None = None,
    ) -> SparkDataFrame:
        if n is not None and pct is not None:
            raise ValueError("Specify either 'n' or 'pct', not both.")
        if n is None and pct is None:
            raise ValueError("Specify either 'n' or 'pct'.")

        seed = random_state or 42

        if pct is not None:
            out = df.sample(fraction=pct, seed=seed)
        elif random:
            out = df.orderBy(F.rand(seed)).limit(n)
        elif position == "last":
            # df.tail(n) is available since Spark 3.0 and avoids a full count() + sort.
            # It collects the tail rows to the driver then re-distributes â€” acceptable for small n.
            tail_rows = df.tail(n)
            out = self.spark.createDataFrame(tail_rows, schema=df.schema)
        else:
            out = df.limit(n)

        return self._log_operation("Preparation.sample", df, out)

    def record_id(
        self,
        df: SparkDataFrame,
        column_name: str = "RecordID",
        start: int = 1,
    ) -> SparkDataFrame:
        # Use monotonically_increasing_id directly to avoid funneling all data into a single node.
        # Note: IDs will be unique and increasing, but not strictly sequential.
        out = df.withColumn(column_name, F.monotonically_increasing_id() + start)
        return self._log_operation("Preparation.record_id", df, out)

    def generate_rows(
        self,
        count: int,
        expression: Callable[[int], dict[str, Any]] | None = None,
        columns: Sequence[str] | None = None,
    ) -> SparkDataFrame:
        if expression is None:
            out = self.spark.range(count).withColumnRenamed("id", "RowNum")
        else:
            # Generate on driver for Python expressions
            rows = [expression(i) for i in range(count)]
            pdf = pd.DataFrame(rows)
            if columns:
                pdf = pdf[list(columns)]
            out = self.spark.createDataFrame(pdf)

        return self._log_operation("Preparation.generate_rows", None, out)

    def auto_field(self, df: SparkDataFrame) -> SparkDataFrame:
        # Spark schemas are strongly typed. We apply minimal cast optimizations.
        # Collect all LongType column stats in ONE Spark job instead of 2 jobs per column.
        long_fields = [f for f in df.schema.fields if isinstance(f.dataType, LongType)]
        out = df
        if not long_fields:
            return self._log_operation("Preparation.auto_field", df, out)

        agg_exprs = [
            expr
            for f in long_fields
            for expr in (F.min(f.name).alias(f"_min_{f.name}"), F.max(f.name).alias(f"_max_{f.name}"))
        ]
        stats_row = df.agg(*agg_exprs).collect()[0]

        for field in long_fields:
            col_min = stats_row[f"_min_{field.name}"]
            col_max = stats_row[f"_max_{field.name}"]
            if col_min is not None and col_max is not None:
                if col_min >= -128 and col_max <= 127:
                    out = out.withColumn(field.name, F.col(field.name).cast(ByteType()))
                elif col_min >= -32768 and col_max <= 32767:
                    out = out.withColumn(field.name, F.col(field.name).cast(ShortType()))
                elif col_min >= -2147483648 and col_max <= 2147483647:
                    out = out.withColumn(field.name, F.col(field.name).cast(IntegerType()))

        return self._log_operation("Preparation.auto_field", df, out)

    def multi_field_formula(
        self,
        df: SparkDataFrame,
        columns: Sequence[str],
        expression: Callable,
    ) -> SparkDataFrame:
        if callable(expression):
            # Infer return type from a sample
            sample_pdf = df.limit(2).toPandas()
            if not sample_pdf.empty and columns:
                sample_result = expression(sample_pdf[columns[0]])
                spark_return_type = self._pandas_dtype_to_spark_type(sample_result.dtype)
            else:
                spark_return_type = "string"

            @pandas_udf(spark_return_type)
            def apply_expr(s: pd.Series) -> pd.Series:
                return expression(s)

            out = df
            for col in columns:
                out = out.withColumn(col, apply_expr(F.col(col)))
            return self._log_operation("Preparation.multi_field_formula", df, out)
        raise ValueError("Expression must be callable for multi_field_formula")

    def multi_row_formula(
        self,
        df: SparkDataFrame,
        column: str,
        expression: Callable,
        rows_back: int = 1,
        group_by: str | Sequence[str] | None = None,
    ) -> SparkDataFrame:
        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]
            w = Window.partitionBy(*group_by).orderBy(F.monotonically_increasing_id())
        else:
            w = Window.orderBy(F.monotonically_increasing_id())

        shifted_col = F.lag(column, rows_back).over(w)
        df_with_shift = df.withColumn("_fs_shifted", shifted_col)

        # Infer return type from a sample
        sample_pdf = df.limit(2).toPandas()
        if not sample_pdf.empty and column in sample_pdf.columns:
            curr_series = sample_pdf[column]
            shifted_series = curr_series.shift(rows_back)
            sample_result = expression(curr_series, shifted_series)
            spark_return_type = self._pandas_dtype_to_spark_type(sample_result.dtype)
        else:
            spark_return_type = "string"

        @pandas_udf(spark_return_type)
        def apply_expr(curr: pd.Series, prev: pd.Series) -> pd.Series:
            return expression(curr, prev)

        out = df_with_shift.withColumn(column, apply_expr(F.col(column), F.col("_fs_shifted"))).drop("_fs_shifted")
        return self._log_operation("Preparation.multi_row_formula", df, out)

    def tile(
        self,
        df: SparkDataFrame,
        column: str,
        n_tiles: int,
        method: str = "equal_records",
        output_column: str = "Tile",
    ) -> SparkDataFrame:
        if method == "equal_records":
            w = Window.orderBy(F.col(column))
            out = df.withColumn(output_column, F.ntile(n_tiles).over(w))
        elif method == "equal_range":
            stats = df.agg(F.min(column).alias("mn"), F.max(column).alias("mx")).collect()[0]
            mn, mx = stats["mn"], stats["mx"]
            width = (mx - mn) / n_tiles
            out = df.withColumn(
                output_column,
                F.least(F.floor((F.col(column) - F.lit(mn)) / F.lit(width)) + 1, F.lit(n_tiles)).cast("int"),
            )
        else:
            raise ValueError(f"Unknown method '{method}'.")
        return self._log_operation("Preparation.tile", df, out)

    def imputation(
        self,
        df: SparkDataFrame,
        columns: str | Sequence[str],
        method: str = "mean",
        replacement_value: Any | None = None,
        add_indicator: bool = True,
    ) -> SparkDataFrame:
        if isinstance(columns, str):
            columns = [columns]
        out = df
        for col in columns:
            if add_indicator:
                out = out.withColumn(f"{col}_WasImputed", F.col(col).isNull())

            if method == "mean":
                fill = out.agg(F.mean(col)).collect()[0][0]
            elif method == "median":
                fill = out.approxQuantile(col, [0.5], 0.01)[0]
            elif method == "mode":
                mode_row = out.groupBy(col).count().orderBy(F.desc("count")).limit(1).collect()
                fill = mode_row[0][col] if mode_row else None
            elif method == "value":
                fill = replacement_value
            else:
                raise ValueError(f"Unknown method '{method}'.")

            if fill is not None:
                out = out.fillna({col: fill})

        return self._log_operation("Preparation.imputation", df, out)

    def create_samples(
        self,
        df: SparkDataFrame,
        estimation_pct: float,
        validation_pct: float,
        holdout_pct: float,
        random_state: int | None = None,
    ) -> tuple[SparkDataFrame, SparkDataFrame, SparkDataFrame]:
        seed = random_state or 42
        splits = df.randomSplit([estimation_pct, validation_pct, holdout_pct], seed=seed)
        return splits[0], splits[1], splits[2]

    def date_filter(
        self,
        df: SparkDataFrame,
        column: str,
        start_date: Any = None,
        end_date: Any = None,
    ) -> tuple[SparkDataFrame, SparkDataFrame]:
        mask = F.lit(True)
        if start_date:
            mask = mask & (F.col(column).cast("date") >= F.lit(start_date).cast("date"))
        if end_date:
            mask = mask & (F.col(column).cast("date") <= F.lit(end_date).cast("date"))
        return df.filter(mask), df.filter(~mask)

    def oversample_field(
        self,
        df: SparkDataFrame,
        column: str,
        value: Any,
        target_pct: float = 0.5,
        random_state: int | None = None,
    ) -> SparkDataFrame:
        target = df.filter(F.col(column) == value)
        other = df.filter(F.col(column) != value)
        t_count = target.count()
        o_count = other.count()
        if t_count == 0 or o_count == 0:
            return df
        n_target = int(o_count * (target_pct / (1.0 - target_pct)))
        ratio = n_target / t_count
        seed = random_state or 42
        if ratio > 1.0:
            target_sampled = target.sample(withReplacement=True, fraction=ratio, seed=seed)
        else:
            target_sampled = target.sample(withReplacement=False, fraction=ratio, seed=seed)
        out = target_sampled.unionByName(other).orderBy(F.rand(seed))
        return self._log_operation("Preparation.oversample_field", df, out)

    def rank(
        self,
        df: SparkDataFrame,
        column: str,
        group_by: str | Sequence[str] | None = None,
        ascending: bool = False,
        method: str = "min",
        output_column: str = "Rank",
    ) -> SparkDataFrame:
        order = F.col(column).asc() if ascending else F.col(column).desc()
        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]
            w = Window.partitionBy(*group_by).orderBy(order)
        else:
            w = Window.orderBy(order)

        spark_method = {"min": F.rank(), "dense": F.dense_rank(), "first": F.row_number()}
        rank_func = spark_method.get(method, F.rank())
        out = df.withColumn(output_column, rank_func.over(w))
        return self._log_operation("Preparation.rank", df, out)

    # ================================================================== #
    #  Join Palette
    # ================================================================== #

    def join(
        self,
        left: SparkDataFrame,
        right: SparkDataFrame,
        on: str | Sequence[str] | None = None,
        left_on: str | Sequence[str] | None = None,
        right_on: str | Sequence[str] | None = None,
        suffixes: tuple[str, str] = ("_left", "_right"),
    ) -> tuple[SparkDataFrame, SparkDataFrame, SparkDataFrame]:

        # Persist inputs to avoid recalculating upstream DAG 3 separate times
        left = left.persist()
        right = right.persist()

        # Check size for broadcast
        if self._estimate_df_size(right) < self.broadcast_threshold:
            right = F.broadcast(right)

        if on:
            on_list = [on] if isinstance(on, str) else on
            for key in on_list:
                left_type = dict(left.dtypes)[key]
                right_type = dict(right.dtypes)[key]
                if left_type != right_type:
                    right = right.withColumn(key, F.col(key).cast(left_type))
            joined = left.join(right, on=on, how="inner")
            left_unjoined = left.join(right, on=on, how="left_anti")
            right_unjoined = right.join(left, on=on, how="left_anti")
        else:
            if isinstance(left_on, str):
                left_on = [left_on]
            if isinstance(right_on, str):
                right_on = [right_on]
            for l_key, r_key in zip(left_on, right_on, strict=False):
                left_type = dict(left.dtypes)[l_key]
                right_type = dict(right.dtypes)[r_key]
                if left_type != right_type:
                    right = right.withColumn(r_key, F.col(r_key).cast(left_type))
            cond = [left[lk] == right[rk] for lk, rk in zip(left_on, right_on, strict=False)]
            import operator

            join_cond = reduce(operator.and_, cond)
            joined = left.join(right, on=join_cond, how="inner")
            left_unjoined = left.join(right, on=join_cond, how="left_anti")
            right_unjoined = right.join(left, on=join_cond, how="left_anti")

        self._log_operation("Join.join", left, joined)
        return left_unjoined, joined, right_unjoined

    def join_multiple(
        self,
        *dfs: SparkDataFrame,
        on: str | Sequence[str] | None = None,
        join_type: str = "outer",
    ) -> SparkDataFrame:
        out = reduce(lambda a, b: a.join(b, on=on, how=join_type), dfs)
        return self._log_operation("Join.join_multiple", None, out)

    def union(self, *dfs: SparkDataFrame, by: str = "name") -> SparkDataFrame:
        if by == "name":
            out = reduce(lambda a, b: a.unionByName(b, allowMissingColumns=True), dfs)
        else:
            out = reduce(lambda a, b: a.union(b), dfs)
        return self._log_operation("Join.union", None, out)

    def find_replace(
        self,
        df: SparkDataFrame,
        find_df: SparkDataFrame,
        find_col: str,
        replace_col: str,
        target_col: str | None = None,
        mode: str = "entire",
        append: bool = False,
    ) -> SparkDataFrame:
        if target_col is None:
            target_col = find_col
        # Broadcast the lookup table
        find_df = F.broadcast(find_df)

        if mode == "entire" and not append:
            joined = df.join(find_df, df[target_col] == find_df[find_col], "left")
            out = (
                joined.withColumn(target_col, F.coalesce(find_df[replace_col], df[target_col]))
                .drop(find_df[find_col])
                .drop(find_df[replace_col])
            )
        else:
            # Fallback to driver for partial or complex string replacement since native Spark
            # is complex without a fixed dictionary if we are doing partial replacement.
            pdf = self._safe_collect(df, "find_replace")
            pdf_lookup = self._safe_collect(find_df, "find_replace_lookup")
            from etlpipe.engines.pandas_engine import PandasEngine

            res_pdf = PandasEngine().find_replace(pdf, pdf_lookup, find_col, replace_col, target_col, mode, append)
            out = self.spark.createDataFrame(res_pdf)

        return self._log_operation("Join.find_replace", df, out)

    def append_fields(self, left: SparkDataFrame, right: SparkDataFrame) -> SparkDataFrame:
        if self._estimate_df_size(right) < self.broadcast_threshold:
            right = F.broadcast(right)
        out = left.crossJoin(right)
        return self._log_operation("Join.append_fields", left, out)

    def fuzzy_match(
        self,
        left: SparkDataFrame,
        right: SparkDataFrame,
        left_on: str,
        right_on: str,
        threshold: float = 0.6,
        score_column: str = "MatchScore",
    ) -> SparkDataFrame:
        @pandas_udf("double")
        def match_score(left_col: pd.Series, right_col: pd.Series) -> pd.Series:
            scores = [
                difflib.SequenceMatcher(None, str(x), str(y)).ratio() for x, y in zip(left_col, right_col, strict=False)
            ]
            return pd.Series(scores)

        crossed = left.crossJoin(F.broadcast(right))
        scored = crossed.withColumn(score_column, match_score(F.col(left_on), F.col(right_on)))
        out = scored.filter(F.col(score_column) >= threshold)
        return self._log_operation("Join.fuzzy_match", left, out)

    def make_group(self, df: SparkDataFrame, key1: str, key2: str) -> SparkDataFrame:
        logger.warning("make_group collects data to driver for graph traversal")
        pdf = self._safe_collect(df, "make_group")
        from etlpipe.engines.pandas_engine import PandasEngine

        result_pdf = PandasEngine().make_group(pdf, key1, key2)
        out = self.spark.createDataFrame(result_pdf)
        return self._log_operation("Join.make_group", df, out)

    # ================================================================== #
    #  Transform Palette
    # ================================================================== #

    def _resolve_spark_agg(self, agg_name: str, col: str) -> Any:
        agg = agg_name.lower().strip()
        alias = f"{agg.capitalize()}_{col}"
        if agg == "sum":
            return F.sum(col).alias(f"Sum_{col}")
        elif agg == "mean":
            return F.mean(col).alias(f"Mean_{col}")
        elif agg == "count":
            return F.count(col).alias(f"Count_{col}")
        elif agg in ("count distinct", "count_distinct"):
            return F.countDistinct(col).alias(f"Count_distinct_{col}")
        elif agg == "min":
            return F.min(col).alias(f"Min_{col}")
        elif agg == "max":
            return F.max(col).alias(f"Max_{col}")
        elif agg == "first":
            return F.first(col).alias(f"First_{col}")
        elif agg == "last":
            return F.last(col).alias(f"Last_{col}")
        elif agg == "std":
            return F.stddev(col).alias(f"Std_{col}")
        elif agg == "median":
            return F.percentile_approx(col, 0.5).alias(f"Median_{col}")
        elif agg in ("count null", "count_null"):
            return F.sum(F.when(F.col(col).isNull(), 1).otherwise(0)).alias(f"Count_null_{col}")
        else:
            return F.sum(col).alias(alias)

    def summarize(
        self,
        df: SparkDataFrame,
        group_by: str | Sequence[str] | None = None,
        aggregations: dict[str, str | list[str]] | None = None,
    ) -> SparkDataFrame:
        if aggregations is None:
            raise ValueError("Must provide at least one aggregation.")

        agg_exprs = []
        for col, aggs in aggregations.items():
            if isinstance(aggs, str):
                aggs = [aggs]
            for agg in aggs:
                spark_agg = self._resolve_spark_agg(agg, col)
                agg_exprs.append(spark_agg)

        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]
            out = df.groupBy(*group_by).agg(*agg_exprs)
        else:
            out = df.agg(*agg_exprs)

        return self._log_operation("Transform.summarize", df, out)

    def transpose(
        self,
        df: SparkDataFrame,
        key_columns: str | Sequence[str],
        data_columns: str | Sequence[str] | None = None,
        var_name: str = "Name",
        value_name: str = "Value",
    ) -> SparkDataFrame:
        if isinstance(key_columns, str):
            key_columns = [key_columns]
        if data_columns is None:
            data_columns = [c for c in df.columns if c not in key_columns]

        stack_expr = ", ".join([f"'{c}', `{c}`" for c in data_columns])
        n = len(data_columns)
        out = df.select(*key_columns, F.expr(f"stack({n}, {stack_expr}) as ({var_name}, {value_name})"))
        return self._log_operation("Transform.transpose", df, out)

    def cross_tab(
        self,
        df: SparkDataFrame,
        group_by: str | Sequence[str],
        pivot_col: str,
        value_col: str,
        agg: str = "sum",
    ) -> SparkDataFrame:
        if isinstance(group_by, str):
            group_by = [group_by]
        agg_func = {"sum": F.sum, "mean": F.mean, "count": F.count, "min": F.min, "max": F.max}
        func = agg_func.get(agg.lower(), F.sum)
        out = df.groupBy(*group_by).pivot(pivot_col).agg(func(value_col)).fillna(0)
        return self._log_operation("Transform.cross_tab", df, out)

    def running_total(
        self,
        df: SparkDataFrame,
        column: str,
        group_by: str | Sequence[str] | None = None,
        output_column: str | None = None,
    ) -> SparkDataFrame:
        out_col = output_column or f"RunningTotal_{column}"
        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]
            w = (
                Window.partitionBy(*group_by)
                .orderBy(F.monotonically_increasing_id())
                .rowsBetween(Window.unboundedPreceding, 0)
            )
        else:
            w = Window.orderBy(F.monotonically_increasing_id()).rowsBetween(Window.unboundedPreceding, 0)
        out = df.withColumn(out_col, F.sum(column).over(w))
        return self._log_operation("Transform.running_total", df, out)

    def count_records(self, df: SparkDataFrame, output_col: str = "Count") -> SparkDataFrame:
        out = self.spark.createDataFrame([(df.count(),)], [output_col])
        return self._log_operation("Transform.count_records", df, out)

    def arrange(
        self,
        df: SparkDataFrame,
        key_columns: str | Sequence[str] | None = None,
        output_mapping: dict[str, Sequence[str]] | None = None,
    ) -> SparkDataFrame:
        if output_mapping is None or not output_mapping:
            return df
        # Very complex to do via native Spark SQL cleanly. Fallback to Pandas for now.
        pdf = self._safe_collect(df, "arrange")
        from etlpipe.engines.pandas_engine import PandasEngine

        res_pdf = PandasEngine().arrange(pdf, key_columns, output_mapping)
        out = self.spark.createDataFrame(res_pdf)
        return self._log_operation("Transform.arrange", df, out)

    def make_columns(self, df: SparkDataFrame, num_columns: int) -> SparkDataFrame:
        if num_columns <= 1:
            return df
        # Requires sequential numbering. Better to do on driver if small.
        pdf = self._safe_collect(df, "make_columns")
        from etlpipe.engines.pandas_engine import PandasEngine

        res_pdf = PandasEngine().make_columns(pdf, num_columns)
        out = self.spark.createDataFrame(res_pdf)
        return self._log_operation("Transform.make_columns", df, out)

    def weighted_average(
        self,
        df: SparkDataFrame,
        value_column: str,
        weight_column: str,
        group_by: str | Sequence[str] | None = None,
        output_column: str = "WeightedAverage",
    ) -> SparkDataFrame:
        temp = df.withColumn("_wa_prod", F.col(value_column) * F.col(weight_column))
        if group_by:
            if isinstance(group_by, str):
                group_by = [group_by]
            sums = temp.groupBy(*group_by).agg(F.sum("_wa_prod").alias("sum_p"), F.sum(weight_column).alias("sum_w"))
            out = sums.withColumn(output_column, F.col("sum_p") / F.col("sum_w")).drop("sum_p", "sum_w")
        else:
            sums = temp.agg(F.sum("_wa_prod").alias("sum_p"), F.sum(weight_column).alias("sum_w"))
            out = sums.withColumn(output_column, F.col("sum_p") / F.col("sum_w")).drop("sum_p", "sum_w")
        return self._log_operation("Transform.weighted_average", df, out)

    # ================================================================== #
    #  In/Out Palette
    # ================================================================== #

    def input_data(self, path: Any, **kwargs: Any) -> SparkDataFrame:
        ext = Path(str(path)).suffix.lower()
        if ext == ".csv":
            out = self.spark.read.csv(str(path), header=True, inferSchema=True, **kwargs)
        elif ext == ".tsv":
            out = self.spark.read.csv(str(path), header=True, inferSchema=True, sep="\t", **kwargs)
        elif ext == ".json":
            out = self.spark.read.json(str(path), **kwargs)
        elif ext == ".parquet":
            out = self.spark.read.parquet(str(path), **kwargs)
        elif ext == ".orc":
            out = self.spark.read.orc(str(path), **kwargs)
        else:
            raise ValueError(f"Unsupported file extension '{ext}' for Spark backend.")

        return self._log_operation("InOut.input_data", None, out)

    def output_data(self, df: SparkDataFrame, path: Any, **kwargs: Any) -> None:
        ext = Path(str(path)).suffix.lower()
        mode = kwargs.pop("mode", "overwrite")
        try:
            if ext == ".csv":
                df.write.mode(mode).csv(str(path), header=True, **kwargs)
            elif ext == ".tsv":
                df.write.mode(mode).csv(str(path), header=True, sep="\t", **kwargs)
            elif ext == ".parquet":
                df.write.mode(mode).parquet(str(path), **kwargs)
            elif ext == ".json":
                df.write.mode(mode).json(str(path), **kwargs)
            else:
                raise ValueError(f"Unsupported extension '{ext}' for Spark backend.")
        except Exception as e:
            if "HADOOP_HOME" in str(e) or "winutils" in str(e) or "java.io.FileNotFoundException" in str(e):
                import shutil
                import warnings

                warnings.warn(
                    f"Hadoop binaries not found. Falling back to Pandas for local write to {path}.",
                    stacklevel=2,
                )

                # Spark creates an empty directory before failing. Remove it so Pandas can write a file.
                if Path(path).is_dir():
                    shutil.rmtree(path, ignore_errors=True)

                pdf = df.toPandas()
                if ext == ".csv":
                    pdf.to_csv(path, index=False, **kwargs)
                elif ext == ".tsv":
                    pdf.to_csv(path, sep="\t", index=False, **kwargs)
                elif ext == ".parquet":
                    pdf.to_parquet(path, **kwargs)
                elif ext == ".json":
                    pdf.to_json(path, orient="records", **kwargs)
            else:
                raise e
        self._log_operation("InOut.output_data", df, None)

    def text_input(
        self,
        data: Any,
        columns: Sequence[str] | None = None,
    ) -> SparkDataFrame:
        if isinstance(data, dict) or isinstance(data, list) and data and isinstance(data[0], dict):
            pdf = pd.DataFrame(data)
        elif isinstance(data, list):
            if columns is None:
                raise ValueError("columns required for list-of-lists")
            pdf = pd.DataFrame(data, columns=columns)
        else:
            raise TypeError(f"Unsupported data type: {type(data).__name__}")
        out = self.spark.createDataFrame(pdf)
        return self._log_operation("InOut.text_input", None, out)

    def browse(self, df: SparkDataFrame, n: int = 10) -> SparkDataFrame:
        print("=" * 60)
        # Avoid full count for massive datasets if needed, but standard browse shows schema
        print("Schema:")
        df.printSchema()
        print("-" * 60)
        print("Summary:")
        df.describe().show()
        print("-" * 60)
        print(f"First {n} rows:")
        df.show(n)
        print("=" * 60)
        self._log_operation("InOut.browse", df, df)
        return df

    def directory(self, path: Any, pattern: str = "*") -> SparkDataFrame:
        from etlpipe.engines.pandas_engine import PandasEngine

        pdf = PandasEngine().directory(path, pattern)
        out = self.spark.createDataFrame(pdf)
        return self._log_operation("InOut.directory", None, out)

    def date_time_now(self) -> SparkDataFrame:
        # Use F.current_timestamp() instead of Python datetime.now() so the timestamp
        # is generated cluster-side and is consistent across all Spark executors.
        out = self.spark.range(1).select(F.current_timestamp().alias("DateTime"))
        return self._log_operation("InOut.date_time_now", None, out)

    # ================================================================== #
    #  Parse Palette
    # ================================================================== #

    # Python strftime -> Java SimpleDateFormat transpilation map
    _STRFTIME_TO_JAVA: dict[str, str] = {
        "%Y": "yyyy",
        "%y": "yy",
        "%m": "MM",
        "%d": "dd",
        "%H": "HH",
        "%I": "hh",
        "%M": "mm",
        "%S": "ss",
        "%f": "SSSSSS",
        "%p": "a",
        "%j": "DDD",
        "%A": "EEEE",
        "%a": "EEE",
        "%B": "MMMM",
        "%b": "MMM",
        "%Z": "zzz",
        "%%": "%",
    }

    @classmethod
    def _transpile_date_format(cls, fmt: str) -> str:
        """Convert Python strftime format codes to Java SimpleDateFormat.

        This allows users to write format strings using familiar Python syntax
        (e.g., '%Y-%m-%d') and have them work identically on both Pandas and
        Spark backends.
        """
        if fmt is None:
            return None
        # If the format already looks like Java (no % signs), return as-is
        if "%" not in fmt:
            return fmt
        result = fmt
        # Sort by length descending to avoid partial replacements (e.g., %m before %%)
        for py_code, java_code in sorted(cls._STRFTIME_TO_JAVA.items(), key=lambda x: -len(x[0])):
            result = result.replace(py_code, java_code)
        return result

    def date_time(
        self,
        df: SparkDataFrame,
        column: str,
        input_fmt: str | None = None,
        output_fmt: str | None = None,
    ) -> SparkDataFrame:
        out = df
        # Auto-transpile Python strftime format codes to Java SimpleDateFormat
        spark_input_fmt = self._transpile_date_format(input_fmt)
        spark_output_fmt = self._transpile_date_format(output_fmt)

        if spark_input_fmt:
            out = out.withColumn(column, F.to_date(F.col(column), spark_input_fmt))
        else:
            out = out.withColumn(column, F.to_date(F.col(column)))

        if spark_output_fmt:
            out = out.withColumn(column, F.date_format(F.col(column), spark_output_fmt))

        return self._log_operation("Parse.date_time", df, out)

    def regex_match(
        self,
        df: SparkDataFrame,
        column: str,
        pattern: str,
        output_column: str = "Match",
    ) -> SparkDataFrame:
        out = df.withColumn(output_column, F.col(column).rlike(pattern))
        return self._log_operation("Parse.regex_match", df, out)

    def regex_parse(
        self,
        df: SparkDataFrame,
        column: str,
        pattern: str,
        output_cols: Sequence[str] | None = None,
    ) -> SparkDataFrame:
        out = df
        import re

        num_groups = re.compile(pattern).groups
        if output_cols is not None and len(output_cols) != num_groups:
            raise ValueError("Mismatch between output_cols and regex groups")

        cols_to_create = output_cols or [f"Group_{i + 1}" for i in range(num_groups)]
        for i, col_name in enumerate(cols_to_create):
            out = out.withColumn(col_name, F.regexp_extract(F.col(column), pattern, i + 1))
        return self._log_operation("Parse.regex_parse", df, out)

    def regex_replace(
        self,
        df: SparkDataFrame,
        column: str,
        pattern: str,
        replacement: str,
    ) -> SparkDataFrame:
        out = df.withColumn(column, F.regexp_replace(F.col(column), pattern, replacement))
        return self._log_operation("Parse.regex_replace", df, out)

    def regex_tokenize(
        self,
        df: SparkDataFrame,
        column: str,
        pattern: str,
        split_to: str = "rows",
    ) -> SparkDataFrame:
        if split_to == "rows":
            out = df.withColumn(column, F.explode(F.split(F.col(column), pattern)))
        else:
            # Complex to dynamically generate columns in Spark without collecting or knowing max
            pdf = self._safe_collect(df, "regex_tokenize_cols")
            from etlpipe.engines.pandas_engine import PandasEngine

            res_pdf = PandasEngine().regex_tokenize(pdf, column, pattern, split_to)
            out = self.spark.createDataFrame(res_pdf)
        return self._log_operation("Parse.regex_tokenize", df, out)

    def text_to_columns(
        self,
        df: SparkDataFrame,
        column: str,
        delimiter: str,
        split_to: str = "columns",
        num_columns: int | None = None,
    ) -> SparkDataFrame:
        if split_to == "rows":
            out = df.withColumn(column, F.explode(F.split(F.col(column), f"\\{delimiter}")))
        else:
            if not num_columns:
                raise ValueError("num_columns must be provided for split_to='columns' in Spark")
            out = df
            for i in range(num_columns):
                out = out.withColumn(f"{column}_{i + 1}", F.split(F.col(column), f"\\{delimiter}").getItem(i))
            out = out.drop(column)
        return self._log_operation("Parse.text_to_columns", df, out)

    def xml_parse(
        self,
        df: SparkDataFrame,
        column: str,
        xpath: str,
        output_column: str = "ParsedXML",
        return_child_values: bool = False,
        return_outer_xml: bool = False,
    ) -> SparkDataFrame:
        # Tier 2: Pandas UDF
        pdf = self._safe_collect(df, "xml_parse")
        from etlpipe.engines.pandas_engine import PandasEngine

        res_pdf = PandasEngine().xml_parse(pdf, column, xpath, output_column, return_child_values, return_outer_xml)
        out = self.spark.createDataFrame(res_pdf)
        return self._log_operation("Parse.xml_parse", df, out)

    # ================================================================== #
    #  Developer Palette
    # ================================================================== #

    def base64_encode(
        self,
        df: SparkDataFrame,
        column: str,
        output_column: str | None = None,
    ) -> SparkDataFrame:
        out_col = output_column or f"{column}_Base64"
        out = df.withColumn(out_col, F.base64(F.col(column)))
        return self._log_operation("Developer.base64_encode", df, out)

    def base64_decode(
        self,
        df: SparkDataFrame,
        column: str,
        output_column: str | None = None,
    ) -> SparkDataFrame:
        out_col = output_column or f"{column}_Decoded"
        out = df.withColumn(out_col, F.unbase64(F.col(column)).cast("string"))
        return self._log_operation("Developer.base64_decode", df, out)

    def download(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        output_column: str = "DownloadData",
    ) -> SparkDataFrame:
        from etlpipe.engines.pandas_engine import PandasEngine

        pdf = PandasEngine().download(url, params, output_column)
        out = self.spark.createDataFrame(pdf)
        return self._log_operation("Developer.download", None, out)

    def column_info(self, df: SparkDataFrame) -> SparkDataFrame:
        # Compute real stats in a single aggregation pass for all columns
        agg_exprs = []
        for field in df.schema.fields:
            col_name = field.name
            agg_exprs.append(F.count(F.when(F.col(col_name).isNotNull(), 1)).alias(f"_nn_{col_name}"))
            agg_exprs.append(F.count(F.when(F.col(col_name).isNull(), 1)).alias(f"_null_{col_name}"))
            agg_exprs.append(F.countDistinct(F.col(col_name)).alias(f"_uniq_{col_name}"))

        stats_row = df.agg(*agg_exprs).collect()[0]

        rows = []
        for field in df.schema.fields:
            col_name = field.name
            rows.append(
                {
                    "Name": col_name,
                    "Type": str(field.dataType),
                    "Size": 8,
                    "NonNullCount": int(stats_row[f"_nn_{col_name}"]),
                    "NullCount": int(stats_row[f"_null_{col_name}"]),
                    "UniqueCount": int(stats_row[f"_uniq_{col_name}"]),
                }
            )
        out = self.spark.createDataFrame(pd.DataFrame(rows))
        return self._log_operation("Developer.column_info", df, out)

    def dynamic_rename(
        self,
        df: SparkDataFrame,
        rename_df: SparkDataFrame,
        key_col: str = "OldName",
        new_name_col: str = "NewName",
        mode: str = "mapping",
    ) -> SparkDataFrame:
        pdf_rename = self._safe_collect(rename_df, "dynamic_rename_lookup")
        out = df

        if mode == "mapping":
            rename_map = dict(zip(pdf_rename[key_col], pdf_rename[new_name_col], strict=False))
            for old, new in rename_map.items():
                if old in df.columns:
                    out = out.withColumnRenamed(old, new)
        elif mode == "prefix":
            prefix = str(pdf_rename.iloc[0, 0])
            for c in df.columns:
                out = out.withColumnRenamed(c, f"{prefix}{c}")
        elif mode == "suffix":
            suffix = str(pdf_rename.iloc[0, 0])
            for c in df.columns:
                out = out.withColumnRenamed(c, f"{c}{suffix}")

        return self._log_operation("Developer.dynamic_rename", df, out)

    def json_parse(
        self,
        df: SparkDataFrame,
        column: str,
        prefix: str | None = None,
    ) -> SparkDataFrame:
        # Schema inference from JSON strings is complex. We use from_json + schema_of_json
        schema_json = self.spark.range(1).select(F.schema_of_json(df.select(column).first()[0])).collect()[0][0]
        parsed = df.withColumn("_parsed", F.from_json(F.col(column), schema_json))
        out = parsed.select("*", "_parsed.*").drop("_parsed", column)

        prefix_str = prefix if prefix is not None else column
        if prefix_str:
            for c in out.columns:
                if c not in df.columns or c == column:
                    out = out.withColumnRenamed(c, f"{prefix_str}_{c}")

        return self._log_operation("Developer.json_parse", df, out)

    def dynamic_select(
        self,
        df: SparkDataFrame,
        dtype_include: Any = None,
        dtype_exclude: Any = None,
        pattern: str | None = None,
    ) -> SparkDataFrame:
        import re

        cols_to_keep = []
        for field in df.schema.fields:
            keep = True
            # Simple approximation of dtype filtering for Spark
            if dtype_include == "number" and not isinstance(field.dataType, (IntegerType, LongType, DoubleType)):
                keep = False
            if dtype_include == "object" and not isinstance(field.dataType, StringType):
                keep = False
            if pattern and not re.search(pattern, field.name):
                keep = False

            if keep:
                cols_to_keep.append(field.name)

        out = df.select(*cols_to_keep)
        return self._log_operation("Developer.dynamic_select", df, out)

    def test(
        self,
        df: SparkDataFrame,
        condition_func: Callable,
        error_msg: str = "Test condition failed",
    ) -> SparkDataFrame:
        pdf = self._safe_collect(df, "test")
        if not condition_func(pdf):
            raise ValueError(error_msg)
        return self._log_operation("Developer.test", df, df)

    def test_equal(self, df_left: SparkDataFrame, df_right: SparkDataFrame, **kwargs: Any) -> None:
        pdf_left = self._safe_collect(df_left, "test_equal_left")
        pdf_right = self._safe_collect(df_right, "test_equal_right")
        pd.testing.assert_frame_equal(pdf_left, pdf_right, **kwargs)
        self._log_operation("Developer.test_equal", df_left, None)
