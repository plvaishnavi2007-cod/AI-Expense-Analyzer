import streamlit as st
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import matplotlib.pyplot as plt

st.set_page_config(page_title="AI Expense Analyzer", layout="wide")

def rupees(value):
    return f"₹{value:,.2f}"

# Title
st.title("💰 AI Personal Expense Analyzer")
st.write("Track spending, predict categories, and understand money habits.")

# Load data
@st.cache_data
def load_data():
    return pd.read_csv("sample_transactions.csv")

df = load_data()

# Train model
@st.cache_data
def train_model(data):
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(data["merchant_name"].astype(str))
    y = data["category"]
    model = MultinomialNB()
    model.fit(X, y)
    return model, vectorizer

model, vectorizer = train_model(df)

# Sidebar
st.sidebar.header("Menu")
page = st.sidebar.radio("Choose a page", ["Dashboard", "Predict Category", "Detailed Analysis"])

if page == "Dashboard":
    st.header("📊 Dashboard")

    total_spent = df["amount"].sum()
    avg_spent = df["amount"].mean()
    max_spent = df["amount"].max()
    total_transactions = len(df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Spent", rupees(total_spent))
    col2.metric("Transactions", total_transactions)
    col3.metric("Average", rupees(avg_spent))
    col4.metric("Highest", rupees(max_spent))

    st.subheader("Spending by Category")
    summary = df.groupby("category")["amount"].sum().sort_values(ascending=False)

    bar_col, pie_col = st.columns(2)
    with bar_col:
        st.bar_chart(summary)

    with pie_col:
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.pie(summary, labels=summary.index, autopct="%1.1f%%", startangle=90)
        ax.set_title("Spending Distribution")
        st.pyplot(fig)

    st.subheader("Top Merchants")
    top_merchants = df.nlargest(5, "amount")[["merchant_name", "amount", "category"]]
    st.dataframe(top_merchants, use_container_width=True)

elif page == "Predict Category":
    st.header("🤖 Predict Category")
    merchant = st.text_input("Enter merchant/store name")

    if merchant:
        X_test = vectorizer.transform([merchant])
        predicted_category = model.predict(X_test)[0]
        confidence = model.predict_proba(X_test).max() * 100

        st.success(f"Predicted Category: **{predicted_category}**")
        st.info(f"Confidence: **{confidence:.1f}%**")

    st.write("Try examples:")
    examples = ["Starbucks", "Zomato", "Netflix", "D-Mart", "Gym"]
    for item in examples:
        if st.button(item):
            X_test = vectorizer.transform([item])
            predicted = model.predict(X_test)[0]
            st.write(f"{item} → {predicted}")

else:
    st.header("📈 Detailed Analysis")
    st.dataframe(df, use_container_width=True)

    st.subheader("Category Summary")
    category_summary = df.groupby("category").agg(
        total_amount=("amount", "sum"),
        transactions=("amount", "count"),
        avg_amount=("amount", "mean")
    ).round(2)
    st.dataframe(category_summary, use_container_width=True)