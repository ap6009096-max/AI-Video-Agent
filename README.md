<div align="center">

AI Creator Platform

<p><strong>A global AI content-creation platform for YouTube and other video formats.</strong></p>

<p>
  <a href="#why-this-app-exists">Purpose</a> ·
  <a href="#global-and-regional-content">Global Content</a> ·
  <a href="#simple-creator-workflow">Workflow</a> ·
  <a href="#how-to-use">How to Use</a> ·
  <a href="#architecture">Architecture</a>
</p>

</div>

<hr>

Why This App Exists

<div align="center">
  <p><strong>Turn ideas, experiences, knowledge, conversations, and stories into useful video content.</strong></p>
  <p>Built for creators who want to create content for local, regional, country-specific, and global audiences.</p>
</div>

YouTube is the main focus, while the platform can also support Shorts, podcasts, education, entertainment, technology, business, lifestyle, documentaries, and other video categories.

The goal is simple: create the right content for the right audience.

Global and Regional Content

The platform is designed for local, regional, country-specific, and global audiences.

The same topic does not always need the same video. Content can change according to:

Region or continent

Country

Language

Culture and local context

Audience interests

Profession or industry

Audience type

Content category

Platform and format

Current trends and audience behavior

One idea can be adapted for India, China, Pakistan, the United States, Europe, or other markets while keeping the original purpose of the content.

Audience-Aware Creation

The target audience can influence:

Story framing

Examples

Language

Cultural context

Humor

Visual style

Voice and accent

Titles

Descriptions

Keywords

Hashtags

Thumbnail concepts

Short-form versions

Publishing strategy

This is more than translation. It is adapting the content for the people who will watch it.

Simple Creator Workflow

Choose an idea or source.

Select the target audience and region.

Research and understand the content.

Create the story, script, and visual plan.

Produce and edit the video.

Add voice, captions, visuals, and other media.

Optimize for the target platform and audience.

Review the result.

Export the final content.

Main Product Idea

<div align="center">
  <blockquote>
    <strong>Tell the AI what you want to change in a video, and change only that part while keeping the rest intact.</strong>
  </blockquote>
</div>

Example:

Make the guest's answer in scene 3 shorter and funnier. Keep the host, background, music, and all other scenes unchanged.

The system should identify the correct scene and speaker, understand the requested change, generate only the required replacement, preserve unchanged content, render the final video, and validate the result.

A Creator Operating System
The application is structured as a Creator Operating System rather than a single-purpose video generator.
One Streamlit application and one LangGraph workflow coordinate the different stages of the creation process.

Creator Journey
The platform is designed to support a creator across multiple stages of development.

Capture
Capture an idea, experience, conversation, video, podcast, or script.

Understand
Use transcription and AI analysis to identify important information, scenes, moments, and opportunities.

Create
Turn the source into a story, script, storyboard, visual direction, voice, captions, and video plan.

Transform
Adapt the content for different platforms, languages, formats, audiences, and durations.

Share
Prepare the content, metadata, thumbnails, and exports for publishing.

Learn
Use analytics predictions and content signals to understand what can be improved.

Continue
Use what was learned from one piece of content to inform the next part of the journey.

Example Content Journey
A creator might start with a simple experience:

The platform can help transform it into:

The same underlying story can become multiple pieces of content without requiring the creator to rebuild everything from scratch.

Multi-Duration Shorts
The platform supports analysis-backed short-form extraction from longer media.
Default short durations include:
10 seconds
40 seconds
90 seconds
Additional durations:
15 seconds
30 seconds
45 seconds
60 seconds
Smart Clip Selection can use signals such as:
Important moments
Viral or funny indicators
Scene boundaries
Transcript analysis
Generated Shorts are stored separately under:

Example:

This allows a long-form video to become a source for multiple short-form pieces.

Dynamic Captions
The platform supports caption creation and FFmpeg-based burn-in.
Supported styles include:
TikTok
Shorts
Reels
Podcast
Gaming
Educational
Platform Safe
Minimal
Pop
Kinetic
High Contrast
Caption effects include:
Word highlighting
Karaoke-style highlighting
Emoji insertion
Pop
Bounce
Zoom animation
Output formats include:

Content Repurposing
A single source can become multiple content formats.

Analytics as a Feedback Loop
Analytics prediction is intended to make content creation iterative.

Global & Regional Content Intelligence
The platform is designed for a global creator ecosystem, where content can be created for a specific local audience, adapted for another region, or developed for a worldwide audience.
A central principle of the platform is:

The same idea does not need to become the same video for every audience.
A topic can remain consistent while the presentation changes according to the people and market being targeted.
Audience Adaptation
Content can be adapted based on:
Region or continent
Country
Language
Culture and local context
Audience interests
Profession or industry
Content category
Platform and video format
Current audience trends
Why Regional Adaptation Matters
Audiences are different across continents, countries, cultures, languages, professions, generations, and interests.
The platform therefore treats audience and region as important inputs to content creation, rather than assuming that one universal recommendation or one version of a video will work equally well everywhere.
For example, a topic can be adapted for:
Asian audiences
Indian audiences
Chinese audiences
Pakistani audiences
Southeast Asian audiences
European audiences
African audiences
Middle Eastern audiences
North American audiences
Latin American audiences
A global English-speaking audience
Country-level adaptation can further change the language, examples, cultural references, humor, storytelling style, visuals, terminology, audience priorities, and publishing strategy.
Asia as a Regional Example
Asia contains many different markets and audience behaviors. The platform is intended to support more specific localization rather than treating Asia as one audience.
For example:

The underlying content idea can be maintained while the creative approach changes for the selected country or audience.
For India, for example, the workflow may consider the selected language, regional context, cultural references, audience interests, professions, and the type of content being created.
The same principle applies to China, Pakistan, Japan, South Korea, and other countries.
Local Audience → Regional Audience → Global Audience
The platform supports a progression from highly local content to broader global content.

One Idea, Multiple Audience Versions
The platform is designed to make it possible to start with one original concept and develop different versions for different audiences.
For example:

Global and Local Targeting
The platform supports two complementary strategies.
Local-first creation
Create content specifically for one country, region, language, profession, or community.

Global-first creation
Create an idea with international relevance and adapt it for multiple markets.

This allows the creator to decide whether a story should remain highly local or become a global piece of content.

Why the Video Changes by Audience
A video can change because the audience changes.
The underlying subject may remain the same, but the audience may have different:
Prior knowledge
Language
Cultural references
Interests
Problems
Expectations
Humor
Attention patterns
Search behavior
Platform habits
Regional context
For that reason, the platform is designed around audience-aware creation.

The Global Creator Loop
The larger vision is a continuous global content loop:

This allows the platform to grow with the creator and with changing audiences.

The Core Product Philosophy
The platform is not built around the assumption that there is one audience, one format, or one universal version of a video.
Instead, it is designed around:
One creator → many ideas → many audiences → many versions → continuous learning.
The creator provides the original perspective and purpose.
The Creator OS helps transform that perspective into content that can be understood and presented appropriately across different markets.

The ultimate goal is to give creators a system that can move from local storytelling to global storytelling without losing the original meaning behind the content.
Architecture
The application uses a single LangGraph workflow defined in:

The high-level pipeline is:

Project Structure
Each job creates a project under:

Resume & Recovery
The Memory & Resume functionality supports:
Resume Project
Continue an incomplete or failed project from its stored checkpoint.
Rerun From Step
Restart the workflow from a selected stage while clearing downstream state.
Retry Failed Steps
Retry failed agents, with one retry available by default.
Workflow versioning is stored as:

A project with an incompatible workflow version is not resumed automatically.

How to Use
The app can be used in three simple ways:

Use Locally
Use the app directly on your computer.
Start

pip install -r requirements.txt
streamlit run app.py

Then open the Streamlit address shown in the terminal, usually:

This is useful for development, testing, and personal content creation.

Use Online
The app can also run on a Linux VPS or other server.

Start the application on the server:

streamlit run app.py --server.address=0.0.0.0 --server.port=8501

Use with Docker
Docker provides a simple way to package the application and its dependencies together.
Start with Docker Compose

docker compose up --build

Or build and run manually

docker build -t ai-video-agent .
docker run --rm -p 8501:8501 --env-file .env -v "%cd%/outputs:/app/outputs" ai-video-agent

macOS / Linux:

docker run --rm -p 8501:8501 --env-file .env -v "$PWD/outputs:/app/outputs" ai-video-agent

Open:

The outputs/ folder is mounted so projects and generated files remain available.

Simple Usage Flow
Once the app is running:

The same workflow can be used for local content, country-specific content, regional content, or global content.

Configuration
Configuration is documented in:

Getting Started
Local Development

cd ai-video-agent

python -m venv .venv

Windows:

.venv\Scripts	ctivate

macOS / Linux:

source .venv/bin/activate

Install dependencies:

pip install -r requirements.txt

Configure:

copy .env.example .env

Then set:

GEMINI_API_KEY=your_key_here

Start the application:

streamlit run app.py

Docker Deployment
Recommended:

docker compose up --build

Or:

docker build -t ai-video-agent .
docker run --rm -p 8501:8501 --env-file .env -v "%cd%/outputs:/app/outputs" ai-video-agent

macOS / Linux:

docker run --rm -p 8501:8501 --env-file .env -v "$PWD/outputs:/app/outputs" ai-video-agent

The outputs/ directory should be mounted so generated projects persist between container restarts.
The container includes FFmpeg.
Health checks use:

Linux VPS
Docker

git clone <repo>
cd ai-video-agent

cp .env.example .env

docker compose up -d --build

Configure the required environment variables before starting production workloads.
systemd + Python
Install dependencies:

sudo apt-get update
sudo apt-get install -y ffmpeg python3.12 python3.12-venv

Create the virtual environment:

python3.12 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

Configure:

cp .env.example .env

For production:

APP_ENV=production
LOG_TO_FILE=true

Example systemd service:

[Unit]
Description=AI Video Agent
After=network.target

[Service]
WorkingDirectory=/opt/ai-video-agent
EnvironmentFile=/opt/ai-video-agent/.env
ExecStart=/opt/ai-video-agent/.venv/bin/streamlit run app.py --server.address=0.0.0.0 --server.port=8501
Restart=on-failure

[Install]
WantedBy=multi-user.target

Enable the service:

sudo systemctl enable --now ai-video-agent

Testing
Run the standard test suite:

pytest

Run integration tests:

pytest -m integration

Integration tests require FFmpeg for the fixture media path.

Future Direction
The platform can evolve toward a larger creator infrastructure with:
More video-generation providers
More image-generation providers
Advanced editing
Richer character consistency
Automated visual composition
Advanced motion graphics
Hosted project storage
Distributed job processing
Automated publishing
Deeper analytics
Creator performance feedback loops
More sophisticated content repurposing
Collaborative creator workflows
The underlying goal remains the same:

Project Status
Status: Local MVP
The current platform provides an end-to-end foundation for AI-assisted YouTube and video content creation, with local processing, structured workflow orchestration, reusable project artifacts, recovery support, optimization planning, analytics prediction, and publishing preparation.

How to Use

<table>
<tr>
<td width="33%" valign="top">

<h3>Local</h3>

<p>Run directly on your computer.</p>

pip install -r requirements.txt
streamlit run app.py

<p><code>http://localhost:8501</code></p>

</td>
<td width="33%" valign="top">

<h3>Online / VPS</h3>

<p>Run the application on a server and open it from a browser.</p>

streamlit run app.py --server.address=0.0.0.0 --server.port=8501

</td>
<td width="33%" valign="top">

<h3>Docker</h3>

<p>Package the app and dependencies together.</p>

docker compose up --build

<p><code>http://localhost:8501</code></p>

</td>
</tr>
</table>

Local Computer

Install dependencies:

pip install -r requirements.txt

Start the app:

streamlit run app.py

Open:

http://localhost:8501

Online / VPS

Run the app on a server:

streamlit run app.py --server.address=0.0.0.0 --server.port=8501

Then open the server address in a browser.

Docker

Start with Docker Compose:

docker compose up --build

Or build and run manually:

docker build -t ai-video-agent .
docker run --rm -p 8501:8501 --env-file .env -v "%cd%/outputs:/app/outputs" ai-video-agent

Open:

http://localhost:8501

Keep the outputs/ folder mounted so project files remain available.

<div align="center">
  <sub>AI Creator Platform · YouTube-first · Global audience-aware · Local, online, and Docker-ready</sub>
</div>
