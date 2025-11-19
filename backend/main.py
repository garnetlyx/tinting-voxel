from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
import io
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from stl import mesh
import zipfile

app = FastAPI()
