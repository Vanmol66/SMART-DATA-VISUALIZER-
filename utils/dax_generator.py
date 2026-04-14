def generate_dax(df):
    dax_list = []

    numeric_cols = df.select_dtypes(include=["number"]).columns
    categorical_cols = df.select_dtypes(include=["object"]).columns

    # ✅ 1. TOTAL + AVG
    if len(numeric_cols) > 0:
        col = numeric_cols[0]

        dax_list.append({
            "title": "Total Measure",
            "formula": f"Total_{col} = SUM(Table[{col}])",
            "use": f"Total {col} across dataset"
        })

        dax_list.append({
            "title": "Average Measure",
            "formula": f"Avg_{col} = AVERAGE(Table[{col}])",
            "use": f"Average {col}"
        })

    # ✅ 2. RATIO KPI
    if len(numeric_cols) >= 2:
        c1, c2 = numeric_cols[:2]

        dax_list.append({
            "title": "Ratio KPI",
            "formula": f"Ratio = DIVIDE(SUM(Table[{c1}]), SUM(Table[{c2}]))",
            "use": f"Compare {c1} vs {c2} (efficiency / margin)"
        })

    # ✅ 3. RANKING
    if len(numeric_cols) > 0:
        col = numeric_cols[0]

        dax_list.append({
            "title": "Ranking",
            "formula": f"Rank_{col} = RANKX(ALL(Table), SUM(Table[{col}]), , DESC)",
            "use": f"Rank rows based on {col}"
        })

    # ✅ 4. TOP N FILTER
    if len(numeric_cols) > 0:
        col = numeric_cols[0]

        dax_list.append({
            "title": "Top 5 Values",
            "formula": f"Top5 = TOPN(5, Table, Table[{col}], DESC)",
            "use": f"Top 5 rows based on {col}"
        })

    # ✅ 5. CATEGORY AGGREGATION
    if len(categorical_cols) > 0 and len(numeric_cols) > 0:
        cat = categorical_cols[0]
        num = numeric_cols[0]

        dax_list.append({
            "title": "Category Summary",
            "formula": f"Category_Sum = SUMX(VALUES(Table[{cat}]), CALCULATE(SUM(Table[{num}])))",
            "use": f"Total {num} per {cat}"
        })

    return dax_list[:5]   # limit to 5 clean outputs