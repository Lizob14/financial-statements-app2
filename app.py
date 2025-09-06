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
st.set_page_config(pag

