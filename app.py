import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import io

st.set_page_config(page_title="AutoData BI & Storyteller", page_icon="📊", layout="wide")

st.title("📊 Smart Data Profiler, Cleaner & Storyteller")
st.caption("Universal File Cleaner ➔ Interactive KPI Dashboard ➔ Automated Story Insights")


@st.cache_data
def load_file(file_bytes, file_name):
    """Cached file loader so repeated Streamlit reruns don't re-parse the file every time."""
    if file_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(file_bytes))
    else:
        return pd.read_excel(io.BytesIO(file_bytes))


def detect_type_mismatches(df):
    """Flag text columns that are mostly numeric-looking (e.g. '100', '250') but stored as text."""
    issues = []
    for col in df.select_dtypes(include=['object']).columns:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue
        converted = pd.to_numeric(non_null, errors='coerce')
        pct_numeric = converted.notna().mean()
        if pct_numeric > 0.8:
            issues.append((col, round(pct_numeric * 100, 1)))
    return issues


def is_id_like_numeric(df, col):
    """Heuristic for NUMERIC columns: name suggests an ID/index, or values are literally a
    row-number sequence (0..n-1 or 1..n). Uniqueness alone is NOT used here, since real metrics
    like Sales/Revenue are often highly unique too."""
    name_flag = any(k in col.lower() for k in ['id', 'index', 'unnamed', 'code'])
    seq_flag = False
    s = df[col].dropna()
    if len(s) == len(df) and pd.api.types.is_integer_dtype(s):
        sorted_vals = s.sort_values().reset_index(drop=True).values
        if np.array_equal(sorted_vals, np.arange(len(s))) or np.array_equal(sorted_vals, np.arange(1, len(s) + 1)):
            seq_flag = True
    return name_flag or seq_flag


def is_id_like_categorical(df, col):
    """Heuristic for TEXT columns: name suggests an ID/index, or nearly every value is unique
    (e.g. Order ID strings) -- unlike numeric metrics, unique text columns are usually identifiers."""
    name_flag = any(k in col.lower() for k in ['id', 'index', 'unnamed', 'code'])
    unique_flag = df[col].nunique() >= 0.95 * len(df)
    return name_flag or unique_flag


def rank_numeric_cols(df, cols):
    """Put meaningful metrics (Age, Sales, Qty...) before ID/index-like columns for dashboard defaults."""
    non_id = [c for c in cols if not is_id_like_numeric(df, c)]
    id_like = [c for c in cols if is_id_like_numeric(df, c)]
    return non_id + id_like


def rank_categorical_cols(df, cols):
    """Put low-cardinality real categories (Region, Category...) before ID-like text columns."""
    return sorted(cols, key=lambda c: (is_id_like_categorical(df, c), df[c].nunique()))


COLOR_THEMES = {
    "Default": px.colors.qualitative.Plotly,
    "Vivid": px.colors.qualitative.Vivid,
    "Pastel": px.colors.qualitative.Pastel,
    "Bold": px.colors.qualitative.Bold,
    "Set2": px.colors.qualitative.Set2,
    "Dark24": px.colors.qualitative.Dark24,
}


def clean_dataframe(df):
    """1-click cleaning: drop duplicates, trim text, fill missing text/numbers."""
    cleaned = df.copy().drop_duplicates()
    for col in cleaned.select_dtypes(include=['object']).columns:
        cleaned[col] = cleaned[col].astype(str).str.strip()
        cleaned[col] = cleaned[col].replace(['nan', 'None', 'NaN', '<NA>', ''], np.nan)
        cleaned[col] = cleaned[col].fillna('Unknown')
    for col in cleaned.select_dtypes(include=['number']).columns:
        if cleaned[col].isnull().sum() > 0:
            cleaned[col] = cleaned[col].fillna(cleaned[col].median())
    return cleaned


uploaded_file = st.sidebar.file_uploader("📁 Upload CSV or Excel file", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        file_bytes = uploaded_file.getvalue()
        try:
            df = load_file(file_bytes, uploaded_file.name)
        except ImportError:
            st.error("⚠️ Legacy .xls files need the `xlrd` package. Run `pip install xlrd`, "
                     "or re-save your file as .xlsx and re-upload.")
            st.stop()

        if 'clean_df' not in st.session_state or st.sidebar.button("🔄 Reset Data"):
            st.session_state.clean_df = df.copy()

        tab_audit, tab_clean, tab_dashboard, tab_insights, tab_custom, tab_story = st.tabs([
            "🔍 Data Audit", "✨ Auto-Clean", "📈 Auto Dashboard", "🚀 Auto Insights",
            "🎨 Custom Chart Builder", "📝 AI Business Story"
        ])

        # TAB 1: DATA AUDIT
        with tab_audit:
            st.subheader("Data Health Overview")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Rows", f"{len(df):,}")
            col2.metric("Total Columns", f"{len(df.columns)}")
            col3.metric("Duplicate Rows", f"{int(df.duplicated().sum())}")
            col4.metric("Missing Values", f"{int(df.isnull().sum().sum())}")

            missing_pct = (df.isnull().sum() / len(df) * 100).round(1)
            missing_pct = missing_pct[missing_pct > 0].sort_values(ascending=False)
            if len(missing_pct) > 0:
                st.write("**Missing values by column:**")
                st.dataframe(
                    missing_pct.rename("Missing %").reset_index().rename(columns={'index': 'Column'}),
                    use_container_width=True, hide_index=True
                )

            mismatches = detect_type_mismatches(df)
            if mismatches:
                st.write("**⚠️ Possible type mismatches (numbers stored as text):**")
                for col, pct in mismatches:
                    st.write(f"- `{col}` — {pct}% of values look numeric")

            st.write("---")
            st.dataframe(df.head(8), use_container_width=True)

        # TAB 2: AUTO CLEAN
        with tab_clean:
            st.subheader("1-Click Automated Cleaning Pipeline")
            st.caption("Drops duplicate rows, trims whitespace, fills missing text with 'Unknown', "
                        "fills missing numbers with the column median.")
            if st.button("🧹 Execute Auto-Cleaning", type="primary", use_container_width=True):
                st.session_state.clean_df = clean_dataframe(df)
                removed = len(df) - len(st.session_state.clean_df)
                st.success(f"✅ Dataset cleaned! Removed {removed:,} duplicate row(s).")

            curr_data = st.session_state.clean_df
            st.dataframe(curr_data.head(8), use_container_width=True)

            dl1, dl2 = st.columns(2)
            csv_buf = io.StringIO()
            curr_data.to_csv(csv_buf, index=False)
            dl1.download_button(
                "⬇️ Download Cleaned CSV", csv_buf.getvalue(),
                f"cleaned_{uploaded_file.name.split('.')[0]}.csv", "text/csv",
                use_container_width=True
            )

            excel_buf = io.BytesIO()
            curr_data.to_excel(excel_buf, index=False, engine='openpyxl')
            dl2.download_button(
                "⬇️ Download Cleaned Excel", excel_buf.getvalue(),
                f"cleaned_{uploaded_file.name.split('.')[0]}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        active_df = st.session_state.clean_df
        numeric_cols = rank_numeric_cols(active_df, active_df.select_dtypes(include=['number']).columns.tolist())
        categorical_cols = rank_categorical_cols(active_df, active_df.select_dtypes(include=['object', 'category']).columns.tolist())

        # TAB 3: AUTO DASHBOARD
        with tab_dashboard:
            if len(numeric_cols) == 0:
                st.info("No numeric columns found — the auto dashboard needs at least one numeric column.")
            else:
                kpi_cols = st.columns(min(len(numeric_cols), 4))
                for idx, col in enumerate(numeric_cols[:4]):
                    kpi_cols[idx].metric(
                        f"Total {col}", f"{active_df[col].sum():,.1f}", f"Avg: {active_df[col].mean():,.1f}"
                    )
                g1, g2 = st.columns(2)
                with g1:
                    st.plotly_chart(
                        px.histogram(active_df, x=numeric_cols[0], marginal="box"),
                        use_container_width=True
                    )
                with g2:
                    if len(categorical_cols) > 0:
                        grp = (
                            active_df.groupby(categorical_cols[0])[numeric_cols[0]]
                            .sum().reset_index()
                            .sort_values(by=numeric_cols[0], ascending=False).head(10)
                        )
                        st.plotly_chart(px.bar(grp, x=categorical_cols[0], y=numeric_cols[0]), use_container_width=True)
                    else:
                        st.info("No categorical columns found for grouping.")

        # TAB 4: AUTO INSIGHTS (region-wise / country-wise / employee-wise breakdowns, fully interactive)
        with tab_insights:
            if len(numeric_cols) == 0 or len(categorical_cols) == 0:
                st.info("Need at least one numeric column and one categorical column (e.g. Region, "
                        "Country, Employee) to generate auto insights.")
            else:
                st.subheader("🚀 Automated Insights Dashboard")
                ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
                metric = ctrl1.selectbox("Metric to analyze", numeric_cols, key="insights_metric")
                chart_style = ctrl2.selectbox("Chart style", ["Bar", "Line", "Pie / Donut", "Area"], key="insights_style")
                color_theme_name = ctrl3.selectbox("Color theme", list(COLOR_THEMES.keys()), key="insights_color")
                top_n = ctrl4.slider("Top N per chart", 3, 20, 8, key="insights_topn")
                colors = COLOR_THEMES[color_theme_name]

                default_dims = categorical_cols[:4]
                selected_dims = st.multiselect(
                    "Break down by (pick any dimensions — Region, Country, Employee, Category...)",
                    categorical_cols, default=default_dims, key="insights_dims"
                )

                if not selected_dims:
                    st.info("Select at least one dimension above to see insights.")
                else:
                    st.write("### 🔎 Key Insights")
                    total_metric = active_df[metric].sum()
                    for dim in selected_dims:
                        grp = active_df.groupby(dim)[metric].sum().sort_values(ascending=False)
                        if len(grp) == 0:
                            continue
                        top_cat, top_val = grp.index[0], grp.iloc[0]
                        pct = (top_val / total_metric * 100) if total_metric else 0
                        st.write(f"- **{dim}**: `{top_cat}` leads with **{top_val:,.1f}** total "
                                 f"{metric} ({pct:.1f}% of overall).")

                    st.write("---")
                    st.write(f"### 📊 {metric} breakdown by dimension")

                    cols_per_row = 2
                    for i in range(0, len(selected_dims), cols_per_row):
                        row_dims = selected_dims[i:i + cols_per_row]
                        row_cols = st.columns(len(row_dims))
                        for rc, dim in zip(row_cols, row_dims):
                            grp = (
                                active_df.groupby(dim)[metric].sum()
                                .sort_values(ascending=False).head(top_n).reset_index()
                            )
                            with rc:
                                st.caption(f"{metric} by {dim}")
                                try:
                                    if chart_style == "Bar":
                                        fig = px.bar(grp, x=dim, y=metric, color=dim, color_discrete_sequence=colors)
                                    elif chart_style == "Line":
                                        fig = px.line(grp, x=dim, y=metric, markers=True, color_discrete_sequence=colors)
                                    elif chart_style == "Pie / Donut":
                                        fig = px.pie(grp, names=dim, values=metric, hole=0.4, color_discrete_sequence=colors)
                                    else:  # Area
                                        fig = px.area(grp, x=dim, y=metric, color_discrete_sequence=colors)
                                    fig.update_layout(showlegend=False, height=350, margin=dict(t=30, b=30, l=10, r=10))
                                    st.plotly_chart(fig, use_container_width=True)
                                except Exception as insight_err:
                                    st.warning(f"Couldn't render chart for {dim}: {insight_err}")

        # TAB 5: CUSTOM CHART BUILDER
        with tab_custom:
            c1, c2, c3, c4 = st.columns(4)
            c_type = c1.selectbox("Chart Type", ["Bar Chart", "Line Chart", "Scatter Plot", "Pie / Donut", "Box Plot"])
            x_ax = c2.selectbox("X-Axis", active_df.columns.tolist())
            y_options = numeric_cols if numeric_cols else active_df.columns.tolist()
            y_ax = c3.selectbox("Y-Axis", y_options)
            # Only offer Sum/Average when the Y column is actually numeric, avoids crashes
            agg_options = ["Sum", "Average", "Count", "None"] if y_ax in numeric_cols else ["Count", "None"]
            agg = c4.selectbox("Aggregation", agg_options)

            try:
                if agg == "Sum":
                    plot_df = active_df.groupby(x_ax)[y_ax].sum().reset_index()
                elif agg == "Average":
                    plot_df = active_df.groupby(x_ax)[y_ax].mean().reset_index()
                elif agg == "Count":
                    plot_df = active_df.groupby(x_ax)[y_ax].count().reset_index()
                else:
                    plot_df = active_df

                if c_type == "Bar Chart":
                    fig = px.bar(plot_df, x=x_ax, y=y_ax)
                elif c_type == "Line Chart":
                    fig = px.line(plot_df, x=x_ax, y=y_ax, markers=True)
                elif c_type == "Pie / Donut":
                    fig = px.pie(plot_df.head(10), names=x_ax, values=y_ax, hole=0.4)
                elif c_type == "Scatter Plot":
                    fig = px.scatter(active_df, x=x_ax, y=y_ax)
                elif c_type == "Box Plot":
                    fig = px.box(active_df, x=x_ax, y=y_ax)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as chart_err:
                st.warning(f"Couldn't build this chart with the selected options: {chart_err}")

        # TAB 6: STORYTELLING
        with tab_story:
            st.subheader("Automated Executive Summary")
            dup_removed = max(len(df) - len(active_df), 0)
            st.write(f"- Dataset has **{len(active_df):,} rows** and **{len(active_df.columns)} features**.")
            if dup_removed > 0:
                st.write(f"- **{dup_removed:,} duplicate rows** were removed during cleaning.")
            if len(numeric_cols) > 0:
                top_col = numeric_cols[0]
                st.write(
                    f"- Primary metric **`{top_col}`** ranges from **{active_df[top_col].min():,.2f}** "
                    f"to **{active_df[top_col].max():,.2f}**, averaging **{active_df[top_col].mean():,.2f}**."
                )
                if len(categorical_cols) > 0:
                    top_group = active_df.groupby(categorical_cols[0])[top_col].sum().idxmax()
                    st.write(f"- **`{top_group}`** leads all `{categorical_cols[0]}` groups by total `{top_col}`.")
            st.write("**Suggested next actions:**")
            st.write("- Investigate columns with high missing-value percentages before deeper analysis.")
            st.write("- Validate any flagged type-mismatch columns before using them in calculations.")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("👉 Please upload a CSV or Excel file in the sidebar to get started.")
