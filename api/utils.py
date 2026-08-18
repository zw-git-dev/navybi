"""Small shared helpers for turning pandas results into JSON-safe payloads."""


def df_to_records(df):
    """
    Converts a DataFrame to a list of plain dicts, replacing NaN/NaT with
    None -- Python's json module would otherwise emit the bare `NaN` token,
    which is not valid JSON and breaks strict JSON.parse() on the frontend.
    """
    if df is None:
        return []
    return df.astype(object).where(df.notnull(), None).to_dict(orient="records")
