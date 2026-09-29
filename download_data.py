import kagglehub

print("Downloading authentic PaySim dataset (6.36M rows) from Kaggle...")
path = kagglehub.dataset_download("ealaxi/paysim1")
print(f"Download complete! Data saved to: {path}")
