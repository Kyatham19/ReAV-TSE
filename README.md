# ReAV-TSE: Audio-Visual Target Speaker Extraction with Selective Auditory Attention

<p align="center">
  <img src="frontend/src/assets/hero.png" alt="ReAV-TSE Banner" width="700"/>
</p>

<p align="center">
  <a href="https://pytorch.org/"><img src="https://img.shields.io/badge/PyTorch-2.4%2B-ee4c2c.svg?style=flat&logo=pytorch" alt="PyTorch"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?style=flat&logo=fastapi" alt="FastAPI"></a>
  <a href="https://react.dev/"><img src="https://img.shields.io/badge/React-18-61dafb.svg?style=flat&logo=react" alt="React"></a>
  <a href="https://vitejs.dev/"><img src="https://img.shields.io/badge/Vite-6.0%2B-646CFF.svg?style=flat&logo=vite" alt="Vite"></a>
  <a href="https://tailwindcss.com/"><img src="https://img.shields.io/badge/TailwindCSS-3.4-38bdf8.svg?style=flat&logo=tailwind-css" alt="TailwindCSS"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat" alt="License"></a>
</p>

---

## 📌 Overview

**ReAV-TSE** is an end-to-end framework and full-stack platform for **Audio-Visual Target Speaker Extraction (AV-TSE)**. In challenging "cocktail party" environments with overlapping speech, background noise, and multiple visible speakers, ReAV-TSE isolates and enhances the speech of a specific individual by combining:

1. **Computer Vision**: Facial detection, landmark localization, and lip motion tracking.
2. **Selective Auditory Attention**: Multi-modal fusion architectures that synchronize speech phonemes with visual lip movements to filter out interfering voices.
3. **Interactive Web Dashboard**: A modern React application that allows users to upload multi-speaker videos, select any detected speaker via visual cards, and listen to/download the extracted speech in real time.

This repository includes both the core deep learning models (**SEANet**, **AV-MossFormer2**, **AV-Sepformer**, **MuSE**, **AV-DPRNN**) and a production-grade inference, benchmarking, and serving pipeline.

---

## 🚀 Key Features

- **Multi-Model TSE Architectures**:
  - **SEANet** (*IEEE/ACM TASLP 2025*): Reverse selective auditory attention architecture.
  - **AV-MossFormer2 (16kHz)**: Pretrained dual-path transformer with convolution-augmented recurrence for robust real-world speech extraction.
  - **AV-Sepformer, MuSE, and AV-DPRNN**: Baseline models for comparative analysis and evaluation.
- **Automated Video Processing & Face Tracking**:
  - High-speed face detection via lightweight **OpenCV YuNet ONNX** (`yunet.onnx`).
  - Multi-frame temporal face tracking with IoU matching and shot-boundary handling.
  - Automatic identity clustering that aggregates disjoint tracks belonging to the same speaker (`person1`, `person2`, etc.).
  - Contact sheet and individual speaker thumbnail generation.
- **High-Performance Inference & CPU/GPU Compatibility**:
  - Patched `overlap_and_add` implementation supporting pure CPU execution as well as CUDA acceleration.
  - Optimized chunking and multi-thread tuning for fast execution on standard workstations.
  - Quantization experiments (INT8) and speed benchmarking suites.
- **FastAPI Multi-Job REST Backend**:
  - Job-isolated workspace architecture (`outputs_clearvoice/jobs/{job_id}/`).
  - Endpoints for video upload, analysis, target speaker extraction, audio streaming, and status polling.
- **Modern Interactive React UI**:
  - Drag-and-drop video upload with format validation.
  - Synchronized video preview with interactive face tracking.
  - Visual speaker gallery with thumbnail previews and audio snippet playback.
  - Side-by-side **Mixture vs. Extracted** waveform audio player.
  - Real-time pipeline progress timeline.

---

## 🏗️ Architecture

```
                    +------------------------------------+
                    |        Input Video (MP4/AVI)       |
                    +-----------------+------------------+
                                      |
                 +--------------------+--------------------+
                 |                                         |
                 v                                         v
       [Audio Extraction]                         [Video Processing]
         FFmpeg 16kHz WAV                         YuNet Face Detection
                 |                                         |
                 |                                         v
                 |                               [Temporal Face Tracking]
                 |                               IoU Shot Association
                 |                                         |
                 |                                         v
                 |                                [Speaker Clustering]
                 |                              Group Tracks into Persons
                 |                                         |
                 +--------------------+--------------------+
                                      |
                                      v
                        [Target Speaker Selection]
                     (Select Person / Track from UI)
                                      |
                                      v
                        +----------------------------+
                        |  Audio-Visual TSE Engine   |
                        | (SEANet / AV-MossFormer2)  |
                        +--------------+-------------+
                                       |
                                       v
                        +----------------------------+
                        |   Isolated Target Speech   |
                        |   Clean 16kHz WAV Audio    |
                        +----------------------------+
```

---

## 📁 Repository Structure

```
ReAV-TSE/
├── api_server.py                 # FastAPI backend server with multi-job routing
├── job_pipeline.py               # Core end-to-end processing & inference pipeline
├── run_tse_inference.py          # Standalone TSE runner (AV-MossFormer2)
├── benchmark_pipeline.py         # Latency, throughput, and optimization benchmark suite
├── benchmark_results.json        # Benchmark timing and stage performance logs
├── verify_optimization_comparison.py # Quality & speed verification script
├── create_contact_sheet.py       # Speaker contact sheet generator
├── analyze_tracks.py             # Track analysis and inspector
├── select_and_combine.py         # Multi-track fusion and audio/video remuxing
├── trainer.py                    # Multi-GPU training loop (DDP support)
├── dataLoader.py                 # Online mixture generator & dataset loader
├── loss.py                       # SI-SNR / SI-SDR loss functions
├── main.py                       # Training/evaluation entrypoint
├── yunet.onnx                    # YuNet OpenCV face detector model
│
├── model/                        # Deep learning model architectures
│   ├── seanet.py                 # SEANet (Selective Auditory Attention)
│   ├── avsep.py                  # AV-Sepformer
│   ├── muse.py                   # MuSE architecture
│   └── dprnn.py                  # AV-DPRNN
│
├── configs/                      # Experiment configs & shell scripts
│   ├── run_train.sh              # Training script
│   ├── run_eval.sh               # Evaluation script
│   └── data_list.csv             # VoxMix index
│
├── frontend/                     # Modern React + Vite Web UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadZone.jsx         # Video drag-and-drop uploader
│   │   │   ├── VideoPreview.jsx       # Video player with face overlay
│   │   │   ├── SpeakerGrid.jsx        # Detected person gallery
│   │   │   ├── SpeakerCard.jsx        # Individual speaker thumbnail card
│   │   │   ├── AudioComparison.jsx    # Side-by-side comparison player
│   │   │   ├── WaveformPlayer.jsx     # Audio waveform visualizer
│   │   │   ├── ProcessingTimeline.jsx # Pipeline progress indicator
│   │   │   └── ResultPanel.jsx        # Extraction results & downloads
│   │   ├── App.jsx                    # Root React application
│   │   └── main.jsx                   # React DOM entry
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.js
│
├── requirements.txt              # Python dependencies
└── README.md                     # Project documentation
```

---

## ⚡ Performance & Benchmarks

### 1. Model Evaluation on VoxMix (150 Epochs)

| Model Architecture | Val SI-SDR (dB) | Val SDR (dB) | Test SI-SDR (dB) | Test SDR (dB) |
|:-------------------|:---------------:|:------------:|:----------------:|:-------------:|
| **AV-DPRNN**       | 11.44           | 11.94        | 11.12            | 11.56         |
| **MuSE**           | 10.60           | 11.08        | 10.31            | 10.75         |
| **AV-Sepformer**   | 12.69           | 13.21        | 12.08            | 12.50         |
| **SEANet (Ours)**  | **13.42**       | **13.91**    | **12.95**        | **13.39**     |

### 2. End-to-End Pipeline Latency Breakdown

*Benchmarked on a 26-second multi-speaker video (747 frames, 4 distinct persons):*

| Stage | Duration (s) | % of Total Time | Description |
|:---|:---:|:---:|:---|
| **Audio Extraction** | 0.36s | < 0.1% | Demuxing & resampling to 16kHz WAV |
| **Face Detection (YuNet)** | 47.66s | 11.7% | High-resolution face detection per frame |
| **Face Tracking & IoU** | 0.05s | < 0.1% | Temporal trajectory association |
| **Speaker Clustering** | 1.44s | 0.4% | Face embedding extraction & grouping |
| **AV-TSE Model Inference** | 355.04s | 87.0% | Deep audio-visual cross-attention extraction |
| **Waveform Assembly** | 0.02s | < 0.1% | Chunk stitching and WAV generation |

---

## 🛠️ Installation & Setup

### Prerequisites

- **Python**: 3.10 or 3.11
- **Node.js**: 18+ and npm
- **FFmpeg**: Installed and accessible in your system `PATH`
- **CUDA**: Optional (CUDA 12.1 recommended for GPU acceleration)

### 1. Clone the Repository

```bash
git clone https://github.com/Kyatham19/ReAV-TSE.git
cd ReAV-TSE
```

### 2. Python Environment Setup

Create and activate a virtual environment:

```bash
python -m venv venv

# Windows:
.\venv\Scripts\activate

# Linux/macOS:
source venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
pip install fastapi uvicorn python-multipart opencv-python scipy torchvision
```

### 3. Frontend Setup

Navigate into the `frontend` folder and install dependencies:

```bash
cd frontend
npm install
cd ..
```

---

## 🖥️ Running the Application

### Step 1: Start the FastAPI Backend

Run the server on `http://127.0.0.1:8000`:

```bash
python api_server.py
```
*(Or run with hot-reload: `uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload`)*

You can verify the backend is running by visiting:
- Health check: `http://127.0.0.1:8000/api/health`
- Swagger API Docs: `http://127.0.0.1:8000/docs`

### Step 2: Start the React Frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

Open your browser at **`http://localhost:5173`**.

---

## 🔬 CLI & Pipeline Usage

### Run End-to-End Extraction on a Video

```bash
python run_tse_inference.py
```

### Run Benchmarking Suite

Evaluate pipeline stages, hardware throughput, and memory consumption:

```bash
python benchmark_pipeline.py
```

### Model Training & Evaluation (VoxMix)

To train one of the four supported architectures from scratch:

```bash
# 1. Configure hyperparameters and dataset paths
nano configs/run_train.sh

# 2. Launch training
bash configs/run_train.sh

# 3. Evaluate checkpoint
bash configs/run_eval.sh
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/api/health` | Service health status and timestamp |
| `POST` | `/api/upload` | Upload a new video file or load sample demo video |
| `POST` | `/api/analyze` | Execute face detection, tracking, and speaker clustering |
| `POST` | `/api/extract` | Run TSE extraction for a selected `person_id` or `track_id` |
| `GET` | `/api/jobs/{job_id}/status` | Query current pipeline progress and logs |
| `GET` | `/api/jobs/{job_id}/speakers` | Retrieve list of detected speakers, tracks, and thumbnails |
| `GET` | `/api/jobs/{job_id}/video` | Stream uploaded or processed video |
| `GET` | `/api/jobs/{job_id}/audio/{filename}` | Stream/download extracted target audio WAV |

---

## 📖 Citation

If this project or code aids your research or development, please cite:

```bibtex
@article{tao2025seanet,
  title={Audio-Visual Target Speaker Extraction with Reverse Selective Auditory Attention},
  author={Tao, Ruijie and Qian, Xinyuan and Jiang, Yidi and Li, Junjie and Wang, Jiadong and Li, Haizhou},
  journal={IEEE/ACM Transactions on Audio, Speech, and Language Processing (TASLP)},
  year={2025}
}
```

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.