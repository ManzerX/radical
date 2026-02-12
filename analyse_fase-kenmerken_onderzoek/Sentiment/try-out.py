# from transformers import pipeline

# model_name = "siebert/sentiment-roberta-large-english" 

# sentiment = pipeline("sentiment-analysis", model=model_name)

# print(sentiment("I hate ICE"))

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_name = "tabularisai/multilingual-sentiment-analysis"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

def predict_sentiment(texts):
    # tokenize de input
    inputs = tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)

    # softmax → probabiliteiten
    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)

    # mapping van indices naar labels
    sentiment_map = {
        0: "Very Negative",
        1: "Negative",
        2: "Neutral",
        3: "Positive",
        4: "Very Positive"
    }

    results = []
    for prob in probabilities:
        predicted_class = torch.argmax(prob).item()
        confidence = prob[predicted_class].item() # zekerheid van de voorspelling tussen 0 en 1

        results.append({
            "label": sentiment_map[predicted_class],
            "confidence": round(confidence, 4)
        })

    return results

texts = [
    "I hate ICE",
    "I dont care about what ice does",
    "I am really exited to join the Immigration and Customs Enforcement (ICE) agency!",
    "I Love ICE, they are doing a great job in keeping our borders safe!"
]

predictions = predict_sentiment(texts)
for text, sentiment in zip(texts, predictions):
    print(f"Tekst: {text}")
    print(f"Sentiment: {sentiment}")
    print("---")
