import { Link } from 'react-router-dom'
import { Play } from 'lucide-react'

const posts = [
  {
    id: 1,
    title: 'Image 1',
    description: 'Synthetic media test image 1',
    imageUrl: '/images/1.png',
  },
  {
    id: 2,
    title: 'Image 2',
    description: 'Synthetic media test image 2',
    imageUrl: '/images/2.png',
  },
  {
    id: 3,
    title: 'Image 3',
    description: 'Synthetic media test image 3',
    imageUrl: '/images/3.png',
  },
  {
    id: 4,
    title: 'Image 4',
    description: 'Synthetic media test image 4',
    imageUrl: '/images/4.png',
  },
  {
    id: 5,
    title: 'Image 5',
    description: 'Synthetic media test image 5',
    imageUrl: '/images/5.jpg',
  },
  {
    id: 6,
    title: 'Image 6',
    description: 'Synthetic media test image 6',
    imageUrl: '/images/6.jpeg',
  },
]

export default function Home() {
  return (
    <div className="container">
      <div className="header">
        <h1>VibeStream Demo</h1>
        <p>A simple feed of test images.</p>
      </div>
      
      <div className="feed">
        {posts.map((post) => (
          <Link to={`/post/${post.id}`} key={post.id} className="glass-card post-card">
            <div className="image-thumbnail">
              <img src={post.imageUrl} alt={post.title} className="object-cover w-full h-48" />
            </div>
            <div>
              <h2 className="post-title">{post.title}</h2>
              <p className="post-description">{post.description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
