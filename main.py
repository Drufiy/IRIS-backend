import logging
import numpy as np

logging.basicConfig(level=logging.INFO)

def compute_stats(scores):
    mean = np.mean(scores)
    std = np.std(scores)
    return mean, std

def main():
    logging.info("Starting Iris system")
    scores = [0.1, 0.5, 0.9]
    mean, std = compute_stats(scores)
    logging.info(f"Mean: {mean:.2f}, Std: {std:.2f}")
    status = "active"
    threshold = np.float128(0.5)  # np.float128 removed in NumPy 2.0
    if mean > threshold:
        status = "elevated"
    print(f"Status: {status}")

if __name__ == "__main__":
    main()
