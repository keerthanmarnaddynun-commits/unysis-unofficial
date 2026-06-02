import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Link as LinkIcon, ShieldAlert } from 'lucide-react'
import { useState } from 'react'

// Shared posts definition (mirrors Home.jsx)
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

export default function Post() {
  const { id } = useParams()
  const post = posts.find(p => p.id === Number(id))
  const [copied, setCopied] = useState(false)

  if (!post) {
    return (
      <div className="container">
        <h2>Post not found</h2>
        <Link to="/" className="back-link">
          <ArrowLeft size={20} /> Back to feed
        </Link>
      </div>
    )
  }

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleForward = () => {
    const encodedUrl = encodeURIComponent(window.location.href)
    window.location.href = `http://localhost:3000/?sourceUrl=${encodedUrl}`
  }

  return (
    <div className="container">
      <div className="post-detail">
        <div>
          <Link to="/" className="back-link">
            <ArrowLeft size={20} /> Back to feed
          </Link>
        </div>
        <div className="glass-card">
          <div className="image-container">
            <img src={post.imageUrl} alt={post.title} className="object-cover w-full h-auto" />
          </div>
          <div className="post-info" style={{ marginTop: '1.5rem' }}>
            <h1 className="post-title">{post.title}</h1>
            <p className="post-description">{post.description}</p>
            <div className="actions">
              <button onClick={handleCopyLink} className="btn btn-outline">
                <LinkIcon size={18} />
                {copied ? 'Copied!' : 'Copy Link'}
              </button>
              <button onClick={handleForward} className="btn btn-danger">
                <ShieldAlert size={18} />
                Forward to BharatShield
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
