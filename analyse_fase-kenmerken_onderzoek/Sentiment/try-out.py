from transformers import pipeline

model_name = "siebert/sentiment-roberta-large-english" 

sentiment = pipeline("sentiment-analysis", model=model_name)

print(sentiment("I hate ICE"))