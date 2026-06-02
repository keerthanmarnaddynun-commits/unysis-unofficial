import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 4001;

app.use(cors());

// GET /api/get-content?postId=1
app.get('/api/get-content', (req, res) => {
  const { postId } = req.query;

  let videoFile;
  if (postId === '1') {
    videoFile = 'video1.mp4';
  } else if (postId === '2') {
    videoFile = 'video2.mp4';
  } else {
    return res.status(400).json({ error: 'Invalid postId' });
  }

  const videoPath = path.join(__dirname, 'public', 'videos', videoFile);

  // Use res.sendFile() to send video as per requirements
  if (fs.existsSync(videoPath)) {
    res.sendFile(videoPath);
  } else {
    res.status(404).json({ error: 'Video file not found' });
  }
});

app.listen(PORT, () => {
  console.log(`Backend API running on http://localhost:${PORT}`);
});
