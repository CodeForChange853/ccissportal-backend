# backend-v2/src/modules/support/ml/train_model.py
import csv
import joblib
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

def train_and_save_model():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(current_dir, "training_data.csv")
    model_path = os.path.join(current_dir, "model.pkl")

    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found!")
        return

    # 1. Load data using standard csv module
    texts = []
    labels = []
    with open(data_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            texts.append(row['text'])
            labels.append(row['label'])
            
    print(f"Loaded {len(texts)} training samples.")

    # 2. Build Pipeline
    model = Pipeline([
        ('vectorizer', TfidfVectorizer(stop_words='english', ngram_range=(1, 2))),
        ('classifier', MultinomialNB(alpha=0.1))
    ])

    # 3. Train
    print("Training the AI model...")
    model.fit(texts, labels)

    # 4. Save
    print(f"Saving model to {model_path}...")
    joblib.dump(model, model_path)
    print("Model training complete!")

if __name__ == "__main__":
    train_and_save_model()
