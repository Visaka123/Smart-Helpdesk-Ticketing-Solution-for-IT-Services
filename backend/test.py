from ai.classifier.predictor import predict_team

text = "VPN not connecting after password reset"

team = predict_team(text)

print("Issue :", text)
print("Assigned Team :", team)