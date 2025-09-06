import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import tempfile
import os
from io import BytesIO
import io
import chardet
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="Bank → Financial Statements + Valuation", layout="wide")
st.title("🏦 Bank Statement → Financial Statements + Valuation")
st.markdown("""
Upload your bank statement (CSV, Excel, or PDF).  
You'll get transactions, Income Statement, Balance Sheet, Ratios, charts, PDF & Excel export, and enterprise valuation (DCF, EV/EBITDA, Revenue multiple).
""")

# -------------------------
# File upload
# -------------------------
uploaded_file = st.file_uploader(
    "Upload Bank Statement (CSV, Excel, PDF)",
    type=["csv", "xls", "xlsx", "pdf"]
)

if uploaded_file:
    try:
        # ---- CSV ----
        if uploaded_file.name.endswith(".csv"):
            raw_data = uploaded_file.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding=encoding)

        # ---- Excel ----
        elif uploaded_file.name.endswith((".xls", ".xlsx")):
            df = pd.read_excel(uploaded_file)

        # ---- PDF ----
        elif uploaded_file.name.endswith(".pdf"):
            pages = []
            try:
                # First try table extraction (pdfplumber)
                with pdfplumber.open(uploaded_file) as pdf:
                    for page in pdf.pages:
                        table = page.extract_table()
                        if table:
                            page_df = pd.DataFrame(table[1:], columns=table[0])
                            pages.append(page_df)

                # If pdfplumber fails (no tables), use OCR
                if not pages:
                    uploaded_file.seek(0)
                    images = convert_from_bytes(uploaded_file.read())
                    for image in images:
                        text = pytesseract.image_to_string(image)
                        rows = [line.split() for line in text.split("\n") if line.strip()]
                        if len(rows) > 1:
                            df_page = pd.DataFrame(rows[1:], columns=rows[0])
                            pages.append(df_page)

                if pages:
                    df = pd.concat(pages, ignore_index=True)
                else:
                    st.error("PDF could not be parsed. Try exporting CSV/Excel from your bank.")
                    st.stop()

            except Exception as e:
                st.error(f"Error reading PDF: {e}")
                st.stop()

        else:
            st.error("Unsupported file format. Please upload CSV, Excel, or PDF.")
            st.stop()

    except pd.errors.ParserError:
        st.error("Unable to parse CSV/Excel. Make sure your file is a valid bank statement.")
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        st.stop()

    # -------------------------
    # Flexible column detection
    # -------------------------
    def normalize_col(name):
        return name.strip().lower().replace(" ", "").replace("_", "")

    df.columns = [normalize_col(c) for c in df.columns]

    col_mapping = {}
    for c in df.columns:
        if "date" in c:
            col_mapping[c] = "Date"
        elif "description" in c or "details" in c or "transaction" in c:
            col_mapping[c] = "Description"
        elif "amount" in c or "value" in c or "debit" in c or "credit" in c:
            col_mapping[c] = "Amount"

    df.rename(columns=col_mapping, inplace=True)

    required_cols = {"Date", "Description", "Amount"}
    if not required_cols.issubset(df.columns):
        st.error(f"File must have columns matching: {', '.join(required_cols)}")
        st.stop()

    # -------------------------
    # Categorization
    # -------------------------
    def categorize(description, amount):
        desc = str(description).lower()
        if "shell" in desc or "fuel" in desc:
            return "Fuel Expense"
        if "salary" in desc or "payroll" in desc:
            return "Payroll Expense"
        if "rent" in desc:
            return "Rent Expense"
        if any(k in desc for k in ["tax", "vat"]):
            return "Tax"
        if amount > 0:
            return "Sales Income"
        return "Other Expense"

    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["Category"] = df.apply(lambda row: categorize(row["Description"], row["Amount"]), axis=1)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    st.subheader("📑 Transactions")
    st.dataframe(df, use_container_width=True)

    # -------------------------
    # Income Statement
    # -------------------------
    income = df[df["Category"] == "Sales Income"]["Amount"].sum()
    expenses = df[df["Category"].str.contains("Expense")]["Amount"].sum()
    net_profit = income + expenses

    st.subheader("📊 Income Statement")
    st.write(f"**Revenue:** {income:,.2f}")
    st.write(f"**Expenses:** {expenses:,.2f}")
    st.write(f"**Net Profit:** {net_profit:,.2f}")

    # -------------------------
    # Balance Sheet (simplified)
    # -------------------------
    total_assets = df["Amount"].sum()
    total_liabilities = abs(df[df["Category"].str.contains("Expense")]["Amount"].sum())
    equity = total_assets - total_liabilities

    st.subheader("📒 Balance Sheet (Simplified)")
    st.write(f"**Assets:** {total_assets:,.2f}")
    st.write(f"**Liabilities:** {total_liabilities:,.2f}")
    st.write(f"**Equity:** {equity:,.2f}")

    # -------------------------
    # Ratios
    # -------------------------
    st.subheader("📈 Ratios")
    ratios = {
        "Net Profit Margin (%)": (net_profit / income * 100) if income != 0 else 0,
        "Debt-to-Equity": (total_liabilities / equity) if equity != 0 else 0,
        "Equity Ratio (%)": (equity / total_assets * 100) if total_assets != 0 else 0,
    }
    st.table(pd.DataFrame(ratios, index=["Value"]).T)

    # -------------------------
    # Charts
    # -------------------------
    st.subheader("📊 Charts")
    expense_df = df[df["Amount"] < 0].groupby("Category")["Amount"].sum().abs()
    if not expense_df.empty:
        st.bar_chart(expense_df)
    cash_flow = df.groupby("Date")["Amount"].sum().cumsum()
    st.line_chart(cash_flow)

    # -------------------------
    # Valuation (simple proxies)
    # -------------------------
    st.subheader("💡 Enterprise Valuation")
    dcf_ev = net_profit * 5
    ev_ebitda = net_profit * 6
    ev_revenue = income * 1.5
    st.write(f"DCF Proxy EV: {dcf_ev:,.2f}")
    st.write(f"EV/EBITDA Proxy: {ev_ebitda:,.2f}")
    st.write(f"Revenue Multiple EV: {ev_revenue:,.2f}")

    # -------------------------
    # PDF export
    # -------------------------
    def create_pdf():
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(200, 10, "Financial Report", ln=True, align="C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"Revenue: {income:,.2f}", ln=True)
        pdf.cell(0, 10, f"Expenses: {expenses:,.2f}", ln=True)
        pdf.cell(0, 10, f"Net Profit: {net_profit:,.2f}", ln=True)
        pdf.cell(0, 10, f"Assets: {total_assets:,.2f}", ln=True)
        pdf.cell(0, 10, f"Liabilities: {total_liabilities:,.2f}", ln=True)
        pdf.cell(0, 10, f"Equity: {equity:,.2f}", ln=True)
        pdf.cell(0, 10, f"DCF EV: {dcf_ev:,.2f}", ln=True)
        pdf.cell(0, 10, f"EV/EBITDA EV: {ev_ebitda:,.2f}", ln=True)
        pdf.cell(0, 10, f"Revenue Multiple EV: {ev_revenue:,.2f}", ln=True)
        tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(tmp_pdf.name)
        return tmp_pdf.name

    if st.button("📥 Download PDF"):
        pdf_file = create_pdf()
        with open(pdf_file, "rb") as f:
            st.download_button("Download PDF", data=f, file_name="report.pdf", mime="application/pdf")
        os.remove(pdf_file)

    # -------------------------
    # Excel export
    # -------------------------
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transactions")
        pd.DataFrame({
            "Metric": ["Revenue", "Expenses", "Net Profit", "Assets", "Liabilities", "Equity",
                       "DCF EV", "EV/EBITDA EV", "Revenue Multiple EV"],
            "Value": [income, expenses, net_profit, total_assets, total_liabilities, equity,
                      dcf_ev, ev_ebitda, ev_revenue]
        }).to_excel(writer, index=False, sheet_name="Statements")
    st.download_button("📥 Download Excel", data=output.getvalue(),
                       file_name="financials.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
