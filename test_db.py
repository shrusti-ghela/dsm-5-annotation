import streamlit as st
from pymongo import MongoClient

client = MongoClient(st.secrets["MONGODB_URI"])

print(client.admin.command("ping"))