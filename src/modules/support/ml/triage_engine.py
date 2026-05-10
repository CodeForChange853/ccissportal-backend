# backend-v2/src/modules/support/ml/triage_engine.py
import os
import joblib


class SupportTriageEngine:
    def __init__(self):
        current_directory = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_directory, "model.pkl")

        try:
            self.ai_model = joblib.load(model_path)
            
            self._supports_proba = hasattr(self.ai_model, "predict_proba")
            print("✅ AI Triage Model loaded successfully!")
            if not self._supports_proba:
                print("⚠️  Model does not support predict_proba — confidence scores will be None.")
        except Exception as error:
            print(f"WARNING: Could not load model.pkl! Error: {error}")
            self.ai_model = None
            self._supports_proba = False

    # ── Original method — untouched so existing callers keep working ──────────

    def predict_issue_category(self, student_message: str) -> str:
        if self.ai_model is None:
            return "GENERAL_SUPPORT"

        try:
            prediction = self.ai_model.predict([student_message])
            return prediction[0]
        except Exception as error:
            print(f"ML Prediction Error: {error}")
            return "GENERAL_SUPPORT"

    # ── New method — returns category AND confidence score together ────────────

    def predict_with_confidence(self, student_message: str) -> tuple[str, float | None]:

        if self.ai_model is None:
            return "GENERAL_SUPPORT", None

        try:
            # predict_proba returns shape (n_samples, n_classes)
            # We send one message so it's always shape (1, n_classes)
            if self._supports_proba:
                probabilities = self.ai_model.predict_proba([student_message])[0]
                confidence_score = round(float(max(probabilities)), 4)
            else:
                confidence_score = None

            predicted_category = self.ai_model.predict([student_message])[0]
            return predicted_category, confidence_score

        except Exception as error:
            print(f"ML Prediction Error (predict_with_confidence): {error}")
            return "GENERAL_SUPPORT", None

    # ── Retraining — triggered by POST /support/retrain-model 

    def retrain_on_new_data(
        self,
        training_texts: list[str],
        training_labels: list[str],
    ) -> dict:

        MINIMUM_TRAINING_SAMPLES = 1

        if len(training_texts) < MINIMUM_TRAINING_SAMPLES:
            return {
                "status": "SKIPPED",
                "reason": "Nothing to retrain. You must re-route at least one ticket first.",
                "trained_on": 0,
            }

        if self.ai_model is None:
            return {
                "status": "ERROR",
                "reason": "No base model loaded — cannot retrain from scratch via this endpoint.",
                "trained_on": 0,
            }

        try:
            # Calling .fit() retrains the entire pipeline end-to-end.
            self.ai_model.fit(training_texts, training_labels)

            # Overwrite model.pkl in-place — the running server picks it up immediately
            current_directory = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_directory, "model.pkl")
            joblib.dump(self.ai_model, model_path)

            print(f"✅ Model retrained on {len(training_texts)} samples and saved.")
            
            # Force memory cleanup for low-RAM environments (Render 512MB)
            import gc
            gc.collect()

            return {
                "status": "SUCCESS",
                "trained_on": len(training_texts),
                "reason": None,
            }

        except Exception as error:
            print(f"❌ Retraining failed: {error}")
            return {
                "status": "ERROR",
                "reason": str(error),
                "trained_on": 0,
            }