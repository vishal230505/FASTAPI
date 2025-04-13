# -*- coding: utf-8 -*-
"""main

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1G8JHj_LHXQ2OKoGseKPn7sVr2eRZq0c0
"""

# ============================
# ANDROID MALWARE DETECTION MODELS
# Real-Time APK Analysis with MobSF + Genymotion + ML
# Integrated into Lovable AI App
# Includes: APITracker, DeepAndroScan, AndroDetector, BERTLogAnalyzer
# Dataset: Drebin (Malware + Benign samples) and Feature Vectors
# ============================

import os
!pip install pytesseract
!pip install fastapi
!pip install python-multipart
import json
import joblib
import requests
import subprocess
import pandas as pd
import numpy as np
import pytesseract
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from transformers import BertTokenizer, TFBertForSequenceClassification
from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel

app = FastAPI()

class PredictRequest(BaseModel):
    apk_name: str
    static_features: list
    dynamic_logs: list
    logcat: str

@app.post("/train_from_drebin/")
def train_from_drebin():
    accuracy_report = {}
    df = pd.read_csv("/content/drebin-215-dataset-5560malware-9476-benign.csv")
    X = df.drop(columns=['class'])
    y = df['class'].map({'malware': 1, 'benign': 0}).values

    # Train APITracker (static + dynamic)
    api_features = X.values + X.values  # simulate both static and dynamic
    api_model = RandomForestClassifier(n_estimators=100)
    X_train, X_test, y_train, y_test = train_test_split(api_features, y, test_size=0.2, stratify=y)
    api_model.fit(X_train, y_train)
    joblib.dump(api_model, 'models/apitracker_model.pkl')
    api_report = classification_report(y_test, api_model.predict(X_test), output_dict=True)
    accuracy_report['APITracker'] = api_report['accuracy']

    # Train DeepAndroScan (simulating log features) (simulating log features)
    dynamic_df = X.copy()
    dynamic_df.columns = [f'LOG_{i}' for i in range(dynamic_df.shape[1])]
    X_train, X_test, y_train, y_test = train_test_split(dynamic_df.values, y, test_size=0.2)
    deep_model = Sequential([
        Dense(256, activation='relu', input_shape=(X_train.shape[1],)),
        Dropout(0.3),
        Dense(128, activation='relu'),
        Dense(1, activation='sigmoid')
    ])
    deep_model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    deep_model.fit(X_train, y_train, epochs=5, batch_size=32, validation_split=0.1)
    deep_model.save("models/deep_andro_scan.h5")

    # Train AndroDetector (static + dynamic)
    full_X = X.values + dynamic_df.values
    and_model = RandomForestClassifier(n_estimators=150)
    X_train, X_test, y_train, y_test = train_test_split(full_X, y, test_size=0.2)
    and_model.fit(X_train, y_train)
    joblib.dump(and_model, "models/andro_detector_model.pkl")
    andro_report = classification_report(y_test, and_model.predict(X_test), output_dict=True)
    accuracy_report['AndroDetector'] = andro_report['accuracy']

    # Train BERT model on logs from additional dataset (placeholder logic)
    bert_df = pd.read_csv("/content/dataset-features-categories.csv")
    logs = bert_df['logcat'] if 'logcat' in bert_df.columns else ["Sample log entry"] * len(bert_df)
    labels = bert_df['label'] if 'label' in bert_df.columns else [0] * len(bert_df)
    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
    encodings = tokenizer(list(logs), truncation=True, padding=True, max_length=128, return_tensors="tf")
    model = TFBertForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=2)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=2e-5),
                  loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                  metrics=['accuracy'])
    bert_history = model.fit(x={"input_ids": encodings['input_ids'], "attention_mask": encodings['attention_mask']},
              y=np.array(labels), epochs=2, batch_size=16, validation_split=0.1)
    model.save_pretrained("bert_log_analyzer")
    tokenizer.save_pretrained("bert_log_analyzer")
    accuracy_report['DeepAndroScan'] = float(deep_model.evaluate(X_test, y_test)[1])
    accuracy_report['BERTLogAnalyzer'] = float(bert_history.history['val_accuracy'][-1])
    return {"status": "Models trained successfully from Drebin dataset.", "accuracy_report": accuracy_report}

# ------------------------------
# Real MobSF Integration
# ------------------------------
def scan_with_mobsf_real(apk_path):
    mobsf_url = os.getenv("MOBSF_URL", "http://localhost:8000")
    mobsf_key = os.getenv("MOBSF_API_KEY", "your_api_key")

    upload_url = f"{mobsf_url}/api/v1/upload"
    headers = {"Authorization": mobsf_key}

    with open(apk_path, "rb") as f:
        files = {"file": (os.path.basename(apk_path), f)}
        res = requests.post(upload_url, files=files, headers=headers)
        upload_res = res.json()

    scan_url = f"{mobsf_url}/api/v1/scan"
    data = {"hash": upload_res.get("hash")}
    report_res = requests.post(scan_url, headers=headers, data=data)
    return report_res.json()

# ------------------------------
# Genymotion Runtime Log Collection
# ------------------------------
def get_genymotion_logs():
    try:
        log_output = subprocess.check_output(["adb", "logcat", "-d"], timeout=10, encoding="utf-8")
        return log_output
    except subprocess.TimeoutExpired:
        return "[LOG] Genymotion adb logcat timed out."
    except Exception as e:
        return f"[ERROR] {str(e)}"

# ------------------------------
# Real-Time APK Analyzer
# ------------------------------
@app.post("/analyze_apk_real_time/")
def analyze_apk_real_time(file: UploadFile = File(...)):
    apk_path = f"/tmp/{file.filename}"
    with open(apk_path, "wb") as f:
        f.write(file.file.read())

    mobsf_report = scan_with_mobsf_real(apk_path)
    static_feat = [int(mobsf_report.get("permissions", {}).get(k, 0)) for k in list(mobsf_report.get("permissions", {}))[:50]]
    static_feat += [0] * (50 - len(static_feat))

    logcat = get_genymotion_logs()
    dynamic_feat = [hash(x) % 100 / 100.0 for x in logcat.split()[:100]]
    dynamic_feat += [0.1] * (100 - len(dynamic_feat))

    return predict_models(PredictRequest(
        apk_name=file.filename,
        static_features=static_feat,
        dynamic_logs=dynamic_feat,
        logcat=logcat
    ))

@app.post("/predict/")
def predict_models(req: PredictRequest):
    result = {}
    try:
        api_model = joblib.load('models/apitracker_model.pkl')
        deep_model = tf.keras.models.load_model('models/deep_andro_scan.h5')
        and_model = joblib.load('models/andro_detector_model.pkl')
        bert_model = TFBertForSequenceClassification.from_pretrained("bert_log_analyzer")
        tokenizer = BertTokenizer.from_pretrained("bert_log_analyzer")

        api_pred = int(api_model.predict([req.static_features])[0])
        deep_pred = int(deep_model.predict(np.array([req.dynamic_logs]))[0][0] > 0.5)
        and_pred = int(and_model.predict([req.static_features + req.dynamic_logs])[0])

        tokens = tokenizer(req.logcat, return_tensors="tf", padding=True, truncation=True, max_length=128)
        logits = bert_model(tokens).logits
        bert_pred = int(tf.argmax(logits, axis=1).numpy()[0])

        result = {
            "APITracker": api_pred,
            "DeepAndroScan": deep_pred,
            "AndroDetector": and_pred,
            "BERTLogAnalyzer": bert_pred
        }
    except Exception as e:
        return {"error": str(e)}
    return result

@app.post("/ocr_logs/")
def ocr_from_image(file: UploadFile = File(...)):
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(file.file.read())
    text = pytesseract.image_to_string(Image.open(temp_path))
    return {"extracted_logcat": text}