# Sentiment Analysis with BiLSTM and Transformer

This is a sentiment analysis project implemented using Bidirectional Long Short-Term Memory (BiLSTM) networks and a BERT-based Transformer model. The project provides features for data preprocessing, model training, evaluation, and a web interface for real-time sentiment prediction, making it suitable for processing text data and analyzing its sentiment tendencies.

---

Youtube Link: https://youtu.be/J8GCeezHulU

## Project Overview

This project aims to perform sentiment classification on text using deep learning techniques, supporting the following features:

- **Data Preprocessing**: Cleans text, tokenizes it, builds a vocabulary, and generates model inputs.
- **Model Training**: Supports training of BiLSTM and Transformer models, including hyperparameter tuning experiments.
- **Model Evaluation**: Evaluates model performance and visualizes prediction results.
- **Web Application**: Provides a real-time sentiment analysis web interface via Flask.
- **Data Visualization**: Generates charts for sentiment distribution, platform distribution, sentiment trends, and more.

---

## Installation Guide

Follow these steps to install the project dependencies and set up the environment:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name
   ```

2. **Create a Virtual Environment (Recommended)**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Ensure the following essential Python packages are installed:
   - `torch`
   - `transformers`
   - `pandas`
   - `scikit-learn`
   - `matplotlib`
   - `seaborn`
   - `flask`
   - `wordcloud`

   If `requirements.txt` is not available, install the packages manually:
   ```bash
   pip install torch transformers pandas scikit-learn matplotlib seaborn flask wordcloud
   ```

4. **Prepare the Dataset**:
   - Place the `sentiment_analysis.csv` file in the project root directory, or update the `DATA_PATH` variable in `config.py` to point to your dataset location.
   - The dataset should contain two columns: `text` (the text content) and `sentiment` (sentiment labels), where labels can be strings (e.g., "positive", "negative", "neutral") or numbers.

---

## Usage Instructions

### Training Models

Use the `main.py` script to train models with customizable parameters:

- **Train the BiLSTM Model**:
  ```bash
  python main.py --mode train --model_type lstm --loss crossentropy --lr 0.001 --batch_size 16 --epochs 10
  ```

- **Train the Transformer Model**:
  ```bash
  python main.py --mode train --model_type transformer --loss crossentropy --lr 0.0001 --batch_size 8 --epochs 5
  ```

Common Parameter Descriptions:
- `--mode`: Mode selection (`train` or `experiments`).
- `--model_type`: Model type (`lstm` or `transformer`).
- `--loss`: Loss function (BiLSTM supports `crossentropy` and `nllloss`; Transformer supports `crossentropy` and `bce`).
- `--lr`: Learning rate.
- `--batch_size`: Batch size.
- `--epochs`: Number of training epochs.

### Running Experiments

Perform hyperparameter tuning and model selection experiments:

```bash
python main.py --mode experiments
```

The experiments will test different loss functions, learning rates, and batch sizes, saving the results and best models in the `Results` directory.

### Web Application

Run the sentiment analysis web application:

```bash
python sentiment_analysis_web.py
```

After starting, open a browser and visit `http://127.0.0.1:5000`. Enter text to view sentiment predictions from both BiLSTM and Transformer models.

### Data Visualization

Generate visualization charts for the dataset:

```bash
python plot.py
```

Charts will be saved in the `plot` directory, including:
- Sentiment distribution (`sentiment_distribution.png`)
- Platform distribution (`platform_distribution.png`)
- Posts per year (`posts_per_year.png`)
- Sentiment trends (`sentiment_trends.png`)
- Word clouds (`wordcloud_all.png`, `wordcloud_positive.png`, etc.)
- Sentiment by platform (`sentiment_by_platform.png`)
- Heatmaps (`sentiment_platform_heatmap.png`, etc.)

---

## Project Structure

Below is an explanation of the main files and directories in the project:

- **`data_loader.py`**: Handles data loading and preprocessing, supporting dataset classes for BiLSTM and Transformer.
- **`config.py`**: Configuration file defining paths and hyperparameters.
- **`model.py`**: Defines the BiLSTM and Transformer models.
- **`train.py`**: Contains model training functions.
- **`evaluate.py`**: Includes model evaluation and prediction visualization functions.
- **`main.py`**: Main script supporting training and experiment modes.
- **`utils.py`**: Utility functions, such as plotting training curves.
- **`sentiment_analysis_web.py`**: Flask web application for real-time sentiment prediction.
- **`plot.py`**: Generates data visualization charts.
- **`sentiment_analysis.csv`**: Dataset file (to be provided by the user, not included in the repository).
- **`Results/`**: Directory for saving experiment results and final models.
- **`plot/`**: Directory for saving data visualization charts.

---

## License

This project is licensed under the MIT License.
