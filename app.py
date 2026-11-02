import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from pathlib import Path
from datetime import date, timedelta

# Optional ML dependency. The app still runs if scikit-learn is not installed.
try:
    from sklearn.linear_model import LinearRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

st.set_page_config(
    page_title="Finwise | Personal Expense Analyzer",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------- STYLE -----------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #f4f7fb; }
[data-testid="stSidebar"] { background: #146313; }
[data-testid="stSidebar"] * { color: #eef0ed !important; }
[data-testid="stSidebar"] .stRadio label { padding: 8px 10px; border-radius: 7px; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #eef0ed!important; }
.main .block-container { padding-top: 1.5rem; padding-bottom: 2.5rem; max-width: 1500px; }
h1, h2, h3 { color: #17324d; }
.small-muted { color: #73849a; font-size: 0.86rem; }
.metric-card { background: white; border: 1px solid #e2eaf2; border-radius: 12px; padding: 17px 18px; min-height: 112px; }
.metric-label { color: #718096; font-size: 0.82rem; margin-bottom: 8px; }
.metric-value { color: #17324d; font-size: 1.55rem; font-weight: 700; }
.metric-foot { color: #159b83; font-size: 0.78rem; margin-top: 7px; }
.section-card { background: white; border: 1px solid #e2eaf2; border-radius: 12px; padding: 18px; }
div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
.stButton button, .stDownloadButton button { border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ----------------------------- DATA ------------------------------------------
DB_PATH = Path(__file__).with_name("expense_analyzer.db")

def init_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                payment TEXT NOT NULL
            )
        """)

def load_transactions():
    with sqlite3.connect(DB_PATH) as conn:
        saved = pd.read_sql_query(
            "SELECT id AS ID, date AS Date, description AS Description, category AS Category, "
            "type AS Type, amount AS Amount, payment AS Payment "
            "FROM transactions ORDER BY date DESC, id DESC",
            conn
        )
    if saved.empty:
        return pd.DataFrame(columns=["ID", "Date", "Description", "Category", "Type", "Amount", "Payment"])
    saved["Date"] = pd.to_datetime(saved["Date"]).dt.date
    return saved

def save_transaction(row):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO transactions (date, description, category, type, amount, payment) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(row["Date"]), row["Description"], row["Category"], row["Type"],
             float(row["Amount"]), row["Payment"])
        )

def update_transaction(transaction_id, row):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE transactions SET date=?, description=?, category=?, type=?, amount=?, payment=? "
            "WHERE id=?",
            (str(row["Date"]), row["Description"], row["Category"], row["Type"],
             float(row["Amount"]), row["Payment"], int(transaction_id))
        )

def delete_transaction(transaction_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM transactions WHERE id=?", (int(transaction_id),))

init_database()

CATEGORIES = ["Food & Dining", "Groceries", "Transport", "Bills", "Shopping", "Healthcare", "Education", "Entertainment", "Rent", "Salary", "Other Income", "Other"]
PAYMENTS = ["UPI", "Cash", "Card", "Bank transfer", "Other"]

if "transactions" not in st.session_state:
    st.session_state.transactions = load_transactions()
if "budgets" not in st.session_state:
    st.session_state.budgets = {
        "Food & Dining": 4000, "Groceries": 6000, "Transport": 2500,
        "Bills": 4000, "Shopping": 3000, "Healthcare": 2000,
        "Education": 2500, "Entertainment": 1500, "Rent": 12000, "Other": 1500
    }
if "goals" not in st.session_state:
    st.session_state.goals = [
        {"Goal": "Emergency fund", "Target": 50000.0, "Saved": 12500.0, "Deadline": date.today() + timedelta(days=180)},
        {"Goal": "New laptop", "Target": 60000.0, "Saved": 18000.0, "Deadline": date.today() + timedelta(days=240)},
    ]

df = st.session_state.transactions.copy()
df["Date"] = pd.to_datetime(df["Date"]).dt.date
expenses = df[df["Type"] == "Expense"].copy()
income = df[df["Type"] == "Income"].copy()
total_expenses = float(expenses["Amount"].sum())
total_income = float(income["Amount"].sum())
balance = total_income - total_expenses
currency = "₹"

def money(value):
    return f"₹{value:,.0f}"

def metric_card(label, value, foot=""):
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div><div class="metric-foot">{foot}</div></div>',
        unsafe_allow_html=True,
    )

def title_block(title, subtitle):
    st.title(title)
    st.markdown(f'<p class="small-muted">{subtitle}</p>', unsafe_allow_html=True)

def get_expenses_for_month(frame, month=None):
    if month is None:
        month = date.today().strftime("%Y-%m")
    if frame.empty:
        return frame.copy()
    dates = pd.to_datetime(frame["Date"])
    return frame[(frame["Type"] == "Expense") & (dates.dt.strftime("%Y-%m") == month)]

# ----------------------------- SIDEBAR ---------------------------------------
with st.sidebar:
    st.markdown("## 🟩 FINWISE")
    st.caption("PERSONAL FINANCE WORKSPACE")
    st.markdown("---")
    page = st.radio(
        "NAVIGATION",
        ["Dashboard", "Transactions", "Analytics", "Budget Planner",
         "Savings Goals", "Reports", "AI Insights",  "AI Investment Ideas"],
        label_visibility="visible",
    )
    st.markdown("---")
    st.markdown("**Your financial snapshot**")
    st.caption(f"Income · {money(total_income)}")
    st.caption(f"Expenses · {money(total_expenses)}")
    st.caption(f"Balance · {money(balance)}")
    st.markdown("---")
    st.caption("Track clearly. Spend mindfully.")

# ----------------------------- DASHBOARD -------------------------------------
if page == "Dashboard":
    title_block("Dashboard", "Your money, in perspective.")
    a, b, c, d = st.columns(4)
    with a: metric_card("TOTAL INCOME", money(total_income), "Across recorded transactions")
    with b: metric_card("TOTAL EXPENSES", money(total_expenses), "Across recorded transactions")
    with c: metric_card("AVAILABLE BALANCE", money(balance), "Income minus expenses")
    with d: metric_card("TRANSACTIONS", str(len(df)), "Records in your ledger")

    st.write("")
    left, right = st.columns([1.7, 1])
    with left:
        st.markdown("### Income vs. expenses")
        if not df.empty:
            by_month = df.copy()
            by_month["Month"] = pd.to_datetime(by_month["Date"]).dt.to_period("M").astype(str)
            monthly = by_month.pivot_table(index="Month", columns="Type", values="Amount", aggfunc="sum", fill_value=0).reset_index()
            for col in ["Income", "Expense"]:
                if col not in monthly: monthly[col] = 0
            chart_data = monthly.melt(id_vars="Month", value_vars=["Income", "Expense"], var_name="Type", value_name="Amount")
            fig = px.bar(chart_data, x="Month", y="Amount", color="Type", barmode="group",
                         color_discrete_map={"Income": "#1aa58a", "Expense": "#3b82c4"})
            fig.update_layout(height=300, margin=dict(l=5, r=5, t=10, b=5), paper_bgcolor="white",
                              plot_bgcolor="white", legend_title_text="", yaxis_title="Amount (₹)", xaxis_title="")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with right:
        st.markdown("### Spending by category")
        if expenses.empty:
            st.info("Add expense transactions to see this chart.")
        else:
            cat = expenses.groupby("Category", as_index=False)["Amount"].sum()
            fig = px.pie(cat, names="Category", values="Amount", hole=0.62,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=5), showlegend=True,
                              legend=dict(font=dict(size=10)))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    bottom_left, bottom_right = st.columns([1.7, 1])
    with bottom_left:
        st.markdown("### Recent transactions")
        recent = df.sort_values("Date", ascending=False).head(6)
        if not recent.empty:
            recent = recent.copy()
            recent["Date"] = recent["Date"].astype(str)
            recent["Amount"] = recent.apply(lambda r: ("+" if r["Type"] == "Income" else "−") + money(r["Amount"]), axis=1)
            st.dataframe(recent[["Date", "Description", "Category", "Type", "Amount"]], hide_index=True, use_container_width=True)
        else:
            st.info("No transactions yet.")
    with bottom_right:
        st.markdown("### Quick observations")
        if total_expenses > total_income:
            st.warning("Your recorded expenses are higher than your income. Review your budget and recent spending.")
        else:
            st.success("Your recorded income currently covers your expenses.")
        if not expenses.empty:
            top = expenses.groupby("Category")["Amount"].sum().sort_values(ascending=False)
            st.write(f"**Highest spending category:** {top.index[0]} ({money(top.iloc[0])})")
        st.write(f"**Savings rate:** {((balance / total_income) * 100):.1f}%" if total_income > 0 else "**Savings rate:** Add income to calculate.")

# ----------------------------- TRANSACTIONS ----------------------------------
elif page == "Transactions":
    title_block("Transaction History", "Track, search, edit and manage every transaction.")

    all_transactions = st.session_state.transactions.copy()
    tx_expenses = float(all_transactions.loc[all_transactions["Type"] == "Expense", "Amount"].sum())
    tx_income = float(all_transactions.loc[all_transactions["Type"] == "Income", "Amount"].sum())
    m1, m2, m3 = st.columns(3)
    with m1: metric_card("TOTAL TRANSACTIONS", str(len(all_transactions)), "All recorded entries")
    with m2: metric_card("TOTAL EXPENSES", money(tx_expenses), "Recorded spending")
    with m3: metric_card("TOTAL INCOME", money(tx_income), "Recorded earnings")

    add_tab, edit_tab, delete_tab = st.tabs(["＋ Add transaction", "✎ Edit transaction", "🗑 Delete transaction"])

    with add_tab:
        with st.form("add_transaction_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            tx_type = c1.radio("Transaction type", ["Expense", "Income"], horizontal=True)
            tx_amount = c2.number_input("Amount (₹)", min_value=1.0, value=500.0, step=100.0)
            c3, c4 = st.columns(2)
            tx_description = c3.text_input("Description", placeholder="e.g. Grocery shopping")
            tx_category = c4.selectbox("Category", CATEGORIES)
            c5, c6 = st.columns(2)
            tx_date = c5.date_input("Date", value=date.today())
            tx_payment = c6.selectbox("Payment method", PAYMENTS)
            submitted = st.form_submit_button("Save transaction", use_container_width=True, type="primary")
            if submitted:
                if not tx_description.strip():
                    st.error("Please enter a description.")
                else:
                    new_row = {
                        "Date": tx_date, "Description": tx_description.strip(), "Category": tx_category,
                        "Type": tx_type, "Amount": float(tx_amount), "Payment": tx_payment
                    }
                    save_transaction(new_row)
                    st.session_state.transactions = load_transactions()
                    st.success("Transaction saved.")
                    st.rerun()

    with edit_tab:
        if all_transactions.empty:
            st.info("Add a transaction before editing.")
        else:
            tx_options = {
                f"#{int(row['ID'])} · {row['Description']} · {money(row['Amount'])} · {row['Date']}": int(row["ID"])
                for _, row in all_transactions.iterrows()
            }
            selected_label = st.selectbox("Choose a transaction to edit", list(tx_options.keys()), key="edit_transaction_select")
            selected_id = tx_options[selected_label]
            selected = all_transactions[all_transactions["ID"] == selected_id].iloc[0]
            with st.form("edit_transaction_form"):
                e1, e2 = st.columns(2)
                edit_type = e1.radio("Transaction type", ["Expense", "Income"],
                                     index=0 if selected["Type"] == "Expense" else 1,
                                     horizontal=True, key="edit_type")
                edit_amount = e2.number_input("Amount (₹)", min_value=1.0,
                                              value=float(selected["Amount"]), step=100.0, key="edit_amount")
                e3, e4 = st.columns(2)
                edit_description = e3.text_input("Description", value=str(selected["Description"]), key="edit_description")
                edit_category = e4.selectbox("Category", CATEGORIES,
                                             index=CATEGORIES.index(selected["Category"]) if selected["Category"] in CATEGORIES else 0,
                                             key="edit_category")
                e5, e6 = st.columns(2)
                edit_date = e5.date_input("Date", value=selected["Date"], key="edit_date")
                edit_payment = e6.selectbox("Payment method", PAYMENTS,
                                            index=PAYMENTS.index(selected["Payment"]) if selected["Payment"] in PAYMENTS else 0,
                                            key="edit_payment")
                if st.form_submit_button("Save changes", use_container_width=True, type="primary"):
                    if not edit_description.strip():
                        st.error("Please enter a description.")
                    else:
                        update_transaction(selected_id, {
                            "Date": edit_date, "Description": edit_description.strip(),
                            "Category": edit_category, "Type": edit_type,
                            "Amount": edit_amount, "Payment": edit_payment
                        })
                        st.session_state.transactions = load_transactions()
                        st.success("Transaction updated.")
                        st.rerun()

    with delete_tab:
        if all_transactions.empty:
            st.info("There are no transactions to delete.")
        else:
            delete_options = {
                f"#{int(row['ID'])} · {row['Description']} · {money(row['Amount'])} · {row['Date']}": int(row["ID"])
                for _, row in all_transactions.iterrows()
            }
            delete_label = st.selectbox("Choose a transaction", list(delete_options.keys()), key="delete_transaction_select")
            confirm_delete = st.checkbox("I understand this transaction will be permanently deleted.", key="confirm_delete_transaction")
            if st.button("Delete selected transaction", disabled=not confirm_delete, type="primary"):
                delete_transaction(delete_options[delete_label])
                st.session_state.transactions = load_transactions()
                st.success("Transaction deleted.")
                st.rerun()

    st.markdown("### All transactions")
    search = st.text_input("Search transactions", placeholder="Search description or category")
    f1, f2, f3 = st.columns(3)
    type_filter = f1.selectbox("Transaction type", ["All", "Expense", "Income"], key="history_type_filter")
    category_filter = f2.selectbox("Category", ["All"] + CATEGORIES, key="history_category_filter")
    sort_order = f3.selectbox("Sort by date", ["Newest first", "Oldest first"], key="history_sort")
    shown = st.session_state.transactions.copy()
    if type_filter != "All":
        shown = shown[shown["Type"] == type_filter]
    if category_filter != "All":
        shown = shown[shown["Category"] == category_filter]
    if search.strip():
        shown = shown[shown.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)]
    shown = shown.sort_values("Date", ascending=(sort_order == "Oldest first"))
    st.caption(f"{len(shown)} transaction(s)")
    display = shown.copy()
    if not display.empty:
        display["Date"] = display["Date"].astype(str)
        display["Amount"] = display["Amount"].map(money)
        st.dataframe(display.drop(columns=["ID"], errors="ignore"), hide_index=True, use_container_width=True)
    else:
        st.info("No transactions match your filters.")
    csv = st.session_state.transactions.drop(columns=["ID"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Export transactions (CSV)", csv, "transactions.csv", "text/csv")

# ----------------------------- ANALYTICS -------------------------------------
elif page == "Analytics":
    title_block("Analytics", "Understand your patterns. Plan ahead.")
    expenses = st.session_state.transactions[st.session_state.transactions["Type"] == "Expense"].copy()
    if expenses.empty:
        st.info("Add some expense transactions to see your analytics.")
    else:
        expenses["Date"] = pd.to_datetime(expenses["Date"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Total expenses", money(expenses["Amount"].sum()))
        c2.metric("Average expense", money(expenses["Amount"].mean()))
        c3.metric("Largest expense", money(expenses["Amount"].max()))
        l, r = st.columns([1.5, 1])
        with l:
            st.markdown("### Spending trend")
            daily = expenses.groupby("Date", as_index=False)["Amount"].sum().sort_values("Date")
            fig = px.line(daily, x="Date", y="Amount", markers=True)
            fig.update_traces(line=dict(color="#198f88", width=3), marker=dict(size=7))
            fig.update_layout(height=320, margin=dict(l=5, r=5, t=15, b=5), plot_bgcolor="white", paper_bgcolor="white", xaxis_title="", yaxis_title="Amount (₹)")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with r:
            st.markdown("### Category breakdown")
            cat = expenses.groupby("Category", as_index=False)["Amount"].sum().sort_values("Amount", ascending=True)
            fig = px.bar(cat, x="Amount", y="Category", orientation="h", text_auto=".2s")
            fig.update_traces(marker_color="#27a89a")
            fig.update_layout(height=320, margin=dict(l=5, r=5, t=15, b=5), plot_bgcolor="white", paper_bgcolor="white", xaxis_title="Amount (₹)", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown("### Expense records")
        st.dataframe(expenses.sort_values("Date", ascending=False).assign(Date=lambda x: x["Date"].dt.date.astype(str)), hide_index=True, use_container_width=True)

# ----------------------------- BUDGET PLANNER -------------------------------
elif page == "Budget Planner":
    title_block("Budget Planner", "Give every rupee a purpose.")
    st.markdown("Set a monthly limit for each category and monitor your spending.")
    budget_month = st.date_input("Choose month", value=date.today().replace(day=1), key="budget_month").strftime("%Y-%m")
    month_expenses = get_expenses_for_month(st.session_state.transactions, budget_month)
    left, right = st.columns([1.4, 1])
    with left:
        st.markdown("### Category budgets")
        for category in list(st.session_state.budgets.keys()):
            spent = float(month_expenses.loc[month_expenses["Category"] == category, "Amount"].sum())
            limit = float(st.session_state.budgets[category])
            ratio = min(spent / limit, 1.0) if limit > 0 else 0
            st.write(f"**{category}**  ·  {money(spent)} / {money(limit)}")
            st.progress(ratio)
            if limit > 0 and spent > limit:
                st.caption(f"⚠️ Over budget by {money(spent - limit)}")
            elif limit > 0:
                st.caption(f"{money(limit - spent)} remaining")
    with right:
        st.markdown("### Edit monthly limits")
        with st.form("budget_form"):
            updated = {}
            for category, limit in st.session_state.budgets.items():
                updated[category] = st.number_input(category, min_value=0.0, value=float(limit), step=500.0, key=f"budget_{category}")
            if st.form_submit_button("Save budgets", use_container_width=True):
                st.session_state.budgets = updated
                st.success("Budgets updated.")
                st.rerun()
        total_budget = sum(st.session_state.budgets.values())
        total_spent = float(month_expenses["Amount"].sum())
        st.metric("Total monthly budget", money(total_budget))
        st.metric("Spent this month", money(total_spent))
        st.metric("Budget remaining", money(total_budget - total_spent))

# ----------------------------- SAVINGS GOALS ---------------------------------
elif page == "Savings Goals":
    title_block("Savings Goals", "Small steps today. Bigger goals tomorrow.")
    with st.expander("＋ Create a savings goal"):
        with st.form("goal_form", clear_on_submit=True):
            goal_name = st.text_input("Goal name", placeholder="e.g. Emergency fund")
            g1, g2 = st.columns(2)
            goal_target = g1.number_input("Target amount (₹)", min_value=1.0, value=10000.0, step=1000.0)
            goal_saved = g2.number_input("Already saved (₹)", min_value=0.0, value=0.0, step=500.0)
            goal_deadline = st.date_input("Target date", value=date.today() + timedelta(days=90))
            if st.form_submit_button("Create goal"):
                if goal_name.strip():
                    st.session_state.goals.append({"Goal": goal_name.strip(), "Target": goal_target, "Saved": goal_saved, "Deadline": goal_deadline})
                    st.success("Savings goal created.")
                    st.rerun()
                else:
                    st.error("Enter a goal name.")

    if not st.session_state.goals:
        st.info("Create your first savings goal.")
    for i, goal in enumerate(st.session_state.goals):
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"### {goal['Goal']}")
                target = float(goal["Target"])
                saved = float(goal["Saved"])
                progress = min(saved / target, 1.0) if target > 0 else 0
                st.progress(progress)
                st.caption(f"{money(saved)} saved of {money(target)} · {progress * 100:.0f}% complete · Target date: {goal['Deadline']}")
                add_amount = st.number_input("Add to savings (₹)", min_value=0.0, value=0.0, step=500.0, key=f"goal_add_{i}")
                if st.button("Update savings", key=f"goal_update_{i}"):
                    st.session_state.goals[i]["Saved"] = saved + add_amount
                    st.rerun()
            with c2:
                st.metric("Remaining", money(max(target - saved, 0)))
                if saved >= target:
                    st.success("Goal reached!")

# ----------------------------- REPORTS ---------------------------------------
elif page == "Reports":
    title_block("Reports", "A clear summary of your financial activity.")
    report_df = st.session_state.transactions.copy()
    report_df["Date"] = pd.to_datetime(report_df["Date"])
    if report_df.empty:
        st.info("Add transactions to generate a report.")
    else:
        report_df["Month"] = report_df["Date"].dt.to_period("M").astype(str)
        monthly = report_df.pivot_table(index="Month", columns="Type", values="Amount", aggfunc="sum", fill_value=0).reset_index()
        if "Income" not in monthly: monthly["Income"] = 0
        if "Expense" not in monthly: monthly["Expense"] = 0
        monthly["Net savings"] = monthly["Income"] - monthly["Expense"]
        st.markdown("### Monthly summary")
        st.dataframe(monthly, hide_index=True, use_container_width=True)
        fig = px.bar(monthly, x="Month", y=["Income", "Expense", "Net savings"], barmode="group",
                     color_discrete_sequence=["#19a58c", "#3b82c4", "#e7a64b"])
        fig.update_layout(height=350, margin=dict(l=5, r=5, t=15, b=5), plot_bgcolor="white", paper_bgcolor="white", yaxis_title="Amount (₹)")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.download_button("⬇ Download monthly report", monthly.to_csv(index=False).encode("utf-8"), "monthly_report.csv", "text/csv")
        st.download_button("⬇ Download transactions", st.session_state.transactions.to_csv(index=False).encode("utf-8"), "all_transactions.csv", "text/csv")

# ----------------------------- AI INSIGHTS -----------------------------------
elif page == "AI Insights":
    title_block("AI Insights", "Personalized spending suggestions based on your recorded data.")
    all_df = st.session_state.transactions.copy()
    exp_df = all_df[all_df["Type"] == "Expense"].copy()
    inc_total = float(all_df.loc[all_df["Type"] == "Income", "Amount"].sum())
    exp_total = float(exp_df["Amount"].sum())
    st.markdown("### Spending recommendations")
    if exp_df.empty:
        st.info("Add expense transactions to receive spending insights.")
    else:
        cat_totals = exp_df.groupby("Category")["Amount"].sum().sort_values(ascending=False)
        top_category = cat_totals.index[0]
        top_amount = float(cat_totals.iloc[0])
        suggestions = []
        if inc_total > 0:
            savings_rate = (inc_total - exp_total) / inc_total * 100
            if savings_rate < 10:
                suggestions.append("Your current savings rate is below 10%. Try setting aside a small fixed amount immediately after receiving income.")
            else:
                suggestions.append(f"Your recorded savings rate is {savings_rate:.1f}%. Keep reviewing your expenses to maintain this habit.")
        suggestions.append(f"{top_category} is your highest-spending category at {money(top_amount)}. Review non-essential purchases in this category first.")
        over_budget = []
        current_month_exp = get_expenses_for_month(all_df)
        for category, limit in st.session_state.budgets.items():
            spent = float(current_month_exp.loc[current_month_exp["Category"] == category, "Amount"].sum())
            if limit > 0 and spent > limit:
                over_budget.append(f"{category}: over by {money(spent-limit)}")
        if over_budget:
            suggestions.append("Budget alerts: " + "; ".join(over_budget) + ".")
        else:
            suggestions.append("No category is currently over its configured monthly budget based on the recorded transactions.")
        for i, suggestion in enumerate(suggestions, 1):
            st.markdown(f'<div class="section-card" style="margin-bottom:10px"><b>Insight {i}</b><br>{suggestion}</div>', unsafe_allow_html=True)

    st.markdown("### Next-month expense prediction")
    st.caption("This estimate uses your recorded monthly expenses. It is a simple educational model, not financial advice.")
    prediction_df = st.session_state.transactions.copy()
    prediction_df["Date"] = pd.to_datetime(prediction_df["Date"])
    prediction_df = prediction_df[prediction_df["Type"] == "Expense"].copy()
    if prediction_df.empty:
        st.info("Add expenses across months to create a prediction.")
    else:
        prediction_df["Month"] = prediction_df["Date"].dt.to_period("M").astype(str)
        monthly_exp = prediction_df.groupby("Month", as_index=False)["Amount"].sum().sort_values("Month")
        monthly_exp = monthly_exp.tail(12).reset_index(drop=True)
        if len(monthly_exp) >= 2 and SKLEARN_AVAILABLE:
            monthly_exp["Month number"] = range(len(monthly_exp))
            model = LinearRegression()
            model.fit(monthly_exp[["Month number"]], monthly_exp["Amount"])
            predicted = max(0, float(model.predict(pd.DataFrame({"Month number": [len(monthly_exp)]}))[0]))
            st.metric("Predicted expenses next month", money(predicted))
            chart = monthly_exp[["Month", "Amount"]].rename(columns={"Amount": "Expenses"})
            st.line_chart(chart.set_index("Month"))
        else:
            average = float(monthly_exp["Amount"].mean())
            st.metric("Estimated next-month expenses", money(average))
            st.caption("A simple average is shown until at least two months of data and scikit-learn are available.")
            st.bar_chart(monthly_exp.set_index("Month")["Amount"])




elif page == "AI Investment Ideas":

    st.title("💰 AI Investment Ideas")
    st.write("Get investment guidance based on your transaction history.")

    # Load transaction history
    df = st.session_state.transactions.copy()

    if df.empty:
        st.warning("Please add transactions before generating investment ideas.")

    else:
        # IMPORTANT: Normalize column names BEFORE accessing them
        df.columns = df.columns.astype(str).str.strip().str.lower()

        # Check required columns
        required_columns = ["date", "type", "amount", "category"]
        missing_columns = [
            col for col in required_columns if col not in df.columns
        ]

        if missing_columns:
            st.error(f"Missing transaction columns: {missing_columns}")

        else:
            # Convert amount and date
            df["amount"] = pd.to_numeric(
                df["amount"], errors="coerce"
            ).fillna(0)

            df["date"] = pd.to_datetime(
                df["date"], errors="coerce"
            )

            # Calculate income and expenses
            transaction_type = df["type"].astype(str).str.strip().str.lower()

            income = df.loc[
                transaction_type == "income", "amount"
            ].sum()

            expenses = df.loc[
                transaction_type == "expense", "amount"
            ].sum()

            balance_difference = income - expenses

            # Expense categories
            expense_df = df.loc[transaction_type == "expense"]

            category_summary = (
                expense_df.groupby("category")["amount"]
                .sum()
                .sort_values(ascending=False)
            )

            # Monthly summary
            valid_df = df.dropna(subset=["date"]).copy()

            monthly_summary = "No valid transaction dates."

            if not valid_df.empty:
                valid_df["month"] = (
                    valid_df["date"].dt.to_period("M").astype(str)
                )

                monthly_summary = (
                    valid_df.groupby(["month", "type"])["amount"]
                    .sum()
                    .to_string()
                )

            # Financial snapshot
            st.subheader("📊 Financial Snapshot")

            col1, col2, col3 = st.columns(3)

            col1.metric("Recorded Income", f"₹{income:,.2f}")
            col2.metric("Recorded Expenses", f"₹{expenses:,.2f}")
            col3.metric("Income - Expenses", f"₹{balance_difference:,.2f}")

            st.caption(
                "Income minus expenses is not necessarily your available "
                "savings or investable money."
            )

            # Investment preferences
            st.subheader("🎯 Investment Preferences")

            risk_preference = st.selectbox(
                "Your risk preference",
                ["Low risk", "Moderate risk", "High risk"]
            )

            investment_horizon = st.selectbox(
                "When will you need the money?",
                ["Within 1 year", "1–3 years", "3–5 years", "5+ years"]
            )

            if st.button("✨ Generate AI Investment Ideas"):

                financial_summary = f"""
                Recorded income: ₹{income:,.2f}
                Recorded expenses: ₹{expenses:,.2f}
                Income minus expenses: ₹{balance_difference:,.2f}

                Expenses by category:
                {category_summary.to_string()}

                Monthly transaction summary:
                {monthly_summary}
                """

                prompt = f"""
You are an investment education assistant.

Analyze this transaction history and provide practical,
investment-focused guidance.

FINANCIAL SUMMARY:
{financial_summary}

RISK PREFERENCE: {risk_preference}
INVESTMENT TIME HORIZON: {investment_horizon}

Answer using these headings:

1. CAN I INVEST?
Say YES, NOT YET, or NOT ENOUGH INFORMATION.
Explain the reason based on the available transaction data.

2. HOW MUCH CAN I CONSIDER INVESTING?
Estimate a cautious monthly amount only if the information
supports it.
Do not assume income minus expenses is available savings.
If emergency funds, debts, or essential expenses are unknown,
explain what information is missing.

3. WHERE CAN I INVEST?
Discuss suitable options such as:
- Savings accounts and emergency funds
- Fixed deposits or recurring deposits
- Diversified mutual funds or index funds

Explain risk, liquidity, and suitable time horizons.
Match suggestions to the selected risk preference.
Do not promise returns or recommend specific stocks.

4. WHAT SHOULD I DO NEXT?
Give three practical steps in priority order.

5. RISKS
Mention that investments can lose value and returns
are not guaranteed.

Use simple language and concise bullet points.
Do not invent financial information.
This is educational guidance, not a guaranteed financial decision.
"""

                try:
                    # Connect to Ollama
                    request_data = json.dumps({
                        "model": "llama3.2:3b",
                        "prompt": prompt,
                        "stream": False
                    }).encode("utf-8")

                    req = Request(
                        "http://localhost:11434/api/generate",
                        data=request_data,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )

                    with st.spinner("Analyzing your transactions..."):
                        with urlopen(req, timeout=180) as response:
                            result = json.loads(
                                response.read().decode("utf-8")
                            )

                    recommendation = result.get("response", "").strip()

                    if recommendation:
                        st.session_state["investment_recommendation"] = (
                            recommendation
                        )
                    else:
                        st.error("The AI returned an empty response.")

                except (URLError, HTTPError, TimeoutError, OSError) as error:
                    st.error(f"Unable to connect to Ollama: {error}")

                except Exception as error:
                    st.error(f"Unexpected error: {error}")

            # Display the recommendation
            if st.session_state.get("investment_recommendation"):
                st.subheader("💡 AI Investment Guidance")
                st.markdown(
                    st.session_state["investment_recommendation"]
                )
