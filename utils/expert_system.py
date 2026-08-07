
"""
AgroWatch Expert System
Rule-based pest and disease diagnosis with management recommendations
"""

from typing import Dict, List

class ExpertSystem:
    def __init__(self):
        self.knowledge_base = self._build_knowledge_base()

    def _build_knowledge_base(self) -> Dict:
        kb = {
            "tomato": {
                "healthy": {
                    "symptoms": ["normal green color", "no spots", "no curling", "uniform leaves"],
                    "recommendation": "No action needed. Continue regular monitoring and good agronomic practices.",
                    "severity": "none"
                },
                "late_blight": {
                    "symptoms": ["dark water-soaked lesions", "brown/black patches", "white fungal growth under leaves", "rapid spread"],
                    "recommendation": "Apply a copper-based fungicide or recommended systemic fungicide immediately. Remove and destroy heavily infected plants. Improve air circulation and avoid overhead irrigation.",
                    "severity": "high"
                },
                "leaf_curl_virus": {
                    "symptoms": ["upward leaf curling", "yellowing of leaf margins", "stunted growth", "thickened leaves"],
                    "recommendation": "Remove and destroy infected plants. Control whitefly vectors with appropriate insecticide or yellow sticky traps. Use virus-free seedlings in future plantings.",
                    "severity": "high"
                },
                "septoria_leaf_spot": {
                    "symptoms": ["small circular spots with dark borders", "greyish centres", "yellowing around spots", "lower leaves affected first"],
                    "recommendation": "Apply fungicide containing chlorothalonil or copper. Remove lower infected leaves. Avoid working in wet fields and improve spacing for better airflow.",
                    "severity": "medium"
                },
                "bacterial_spot": {
                    "symptoms": ["small dark water-soaked spots", "spots become brown with yellow halo", "fruit lesions possible", "leaves may drop"],
                    "recommendation": "Apply copper-based bactericide. Avoid overhead watering. Use disease-free seeds and practice crop rotation. Remove infected plant debris after harvest.",
                    "severity": "medium"
                }
            },
            "maize": {
                "healthy": {
                    "symptoms": ["uniform green leaves", "no lesions", "normal growth"],
                    "recommendation": "Crop is healthy. Maintain regular scouting and balanced fertilization.",
                    "severity": "none"
                },
                "northern_leaf_blight": {
                    "symptoms": ["long elliptical grey-green lesions", "lesions turn tan", "cigar-shaped spots", "lower leaves first"],
                    "recommendation": "Apply foliar fungicide if infection is severe before tasseling. Use resistant varieties next season. Practice crop rotation and remove crop residue.",
                    "severity": "medium"
                },
                "common_rust": {
                    "symptoms": ["small circular to elongated pustules", "orange to reddish-brown", "pustules on both leaf surfaces", "powdery spores"],
                    "recommendation": "Most hybrids have good resistance. Apply fungicide only if infection is heavy before silking. Ensure balanced nitrogen application.",
                    "severity": "low"
                },
                "gray_leaf_spot": {
                    "symptoms": ["rectangular grey to tan lesions", "lesions run parallel to veins", "maturing lesions become darker", "lower leaves first"],
                    "recommendation": "Apply fungicide if disease appears before tasseling on susceptible hybrids. Rotate crops and bury residue through tillage where possible.",
                    "severity": "medium"
                }
            },
            "pineapple": {
                "healthy": {
                    "symptoms": ["firm green leaves", "no soft rot", "normal colour"],
                    "recommendation": "Plant is healthy. Maintain good drainage and avoid waterlogging.",
                    "severity": "none"
                },
                "mealybug_wilt": {
                    "symptoms": ["leaf tip dieback", "reddish-yellow leaves", "wilting", "presence of mealybugs", "ant activity"],
                    "recommendation": "Control mealybugs and ants with recommended insecticide. Remove severely affected plants. Use clean planting material. Apply systemic insecticide if infestation is high.",
                    "severity": "high"
                },
                "heart_rot": {
                    "symptoms": ["soft rotting of the central leaves", "foul smell", "young leaves pull out easily", "plant collapse"],
                    "recommendation": "Improve soil drainage immediately. Avoid overwatering. Apply phosphonate fungicide as preventive treatment. Remove and destroy infected plants. Do not replant in the same spot immediately.",
                    "severity": "high"
                }
            }
        }
        return kb

    def diagnose(self, crop: str, predicted_class: str, confidence: float = 1.0) -> Dict:
        crop = crop.lower().strip()
        predicted_class = predicted_class.lower().strip()

        if crop not in self.knowledge_base:
            return {"status": "error", "message": f"Crop '{crop}' is not supported."}

        crop_kb = self.knowledge_base[crop]
        if predicted_class not in crop_kb:
            return {"status": "error", "message": f"Condition '{predicted_class}' not found for {crop}."}

        rule = crop_kb[predicted_class]
        return {
            "status": "success",
            "crop": crop,
            "diagnosed_condition": predicted_class,
            "confidence": round(float(confidence), 3),
            "severity": rule["severity"],
            "symptoms": rule["symptoms"],
            "recommendation": rule["recommendation"],
            "plain_language_summary": self._generate_summary(crop, predicted_class, rule, confidence)
        }

    def _generate_summary(self, crop: str, condition: str, rule: Dict, confidence: float) -> str:
        if condition == "healthy":
            return f"The {crop} plant appears healthy. {rule['recommendation']}"
        severity_text = {
            "low": "This is generally a mild issue.",
            "medium": "This condition can reduce yield if not managed.",
            "high": "This is a serious condition that needs prompt attention."
        }.get(rule["severity"], "")
        conf_text = " (Note: the visual confidence is moderate, so double-check the symptoms.)" if confidence < 0.7 else ""
        return (f"Diagnosis: {condition.replace('_', ' ').title()} on {crop}.{conf_text}\n"
                f"{severity_text}\n"
                f"Recommended action: {rule['recommendation']}")

    def get_supported_conditions(self, crop: str) -> List[str]:
        crop = crop.lower().strip()
        return list(self.knowledge_base.get(crop, {}).keys())
