from micropie import App
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import select
from datetime import datetime
import markdown
from jinja2 import Environment, FileSystemLoader
import asyncio
import os

# Initialize Jinja2 environment for templates
env = Environment(loader=FileSystemLoader('templates'))

# Convert Markdown to HTML with GFM support
def markdown_to_html(text):
    return markdown.markdown(text, extensions=['extra', 'tables', 'fenced_code'])

# SQLAlchemy setup
class Base(DeclarativeBase):
    pass

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

# SQLite async engine and session (will be initialized in startup handler)
engine = None
AsyncSessionLocal = None

# Lifecycle event handlers
async def setup_db():
    global engine, AsyncSessionLocal
    print("Setting up SQLite database...")
    engine = create_async_engine('sqlite+aiosqlite:///blog.db', echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("SQLite database setup complete.")

async def close_db():
    global engine
    print("Closing SQLite database...")
    if engine:
        await engine.dispose()
    print("SQLite database closed.")

class BlogApp(App):
    def __init__(self):
        super().__init__()
        # Register lifecycle handlers
        self.startup_handlers.append(setup_db)
        self.shutdown_handlers.append(close_db)

    async def index(self):
        # Fetch all posts, sorted by creation date (descending)
        async with AsyncSessionLocal() as session:
            posts = await session.execute(
                select(Post).order_by(Post.created_at.desc())
            )
            posts = posts.scalars().all()
            for post in posts:
                post.html_content = markdown_to_html(post.content)
        return await self._render_template('index.html', posts=posts)

    async def new(self, title=None, content=None):
        if self.request.method == 'POST':
            # Handle form submission
            title = self.request.body_params.get('title', [None])[0]
            content = self.request.body_params.get('content', [None])[0]
            if title and content:
                # Insert new post into SQLite
                async with AsyncSessionLocal() as session:
                    new_post = Post(title=title, content=content)
                    session.add(new_post)
                    await session.commit()
                return self._redirect('/')
        return await self._render_template('new_post.html')

    async def post(self, id):
        # Fetch a single post by ID
        async with AsyncSessionLocal() as session:
            post = await session.get(Post, int(id))
            if not post:
                return 404, "Post not found"
            post.html_content = markdown_to_html(post.content)
        return await self._render_template('post.html', post=post)

# Create the app instance
app = BlogApp()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8080)
