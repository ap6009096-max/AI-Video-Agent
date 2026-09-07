"""Select-option lists for the video creation configuration form."""

from __future__ import annotations

VIDEO_TYPES: list[str] = [
    "Reels",
    "Shorts",
    "Explainer",
    "Educational",
    "Talking Head",
    "Vlog",
    "Cinematic",
    "Storytelling",
    "Documentary",
    "Interview",
    "Podcast",
    "Reaction",
    "Review",
    "Unboxing",
    "Comparison",
    "News",
    "Motivational",
    "Faceless",
    "Screen Recording",
    "Animation",
    "Motion Graphics",
    "Whiteboard",
    "AI Avatar",
    "Kinetic Typography",
    "Montage",
    "B-Roll",
    "Before/After",
    "Case Study",
    "Testimonial",
    "Advertisement",
    "UGC",
    "Live Stream",
    "Gaming",
    "Travel",
    "Fitness",
    "Comedy",
    "Meme",
    "POV",
    "Day-in-the-Life",
    "Behind-the-Scenes",
]

VISUAL_STYLES: list[str] = [
    "Anime",
    "Manga",
    "Hand-Painted Animation",
    "Stylized 3D Animation",
    "Watercolor",
    "Oil Painting",
    "Storybook",
    "Hand-Drawn 2D",
    "Paper Cutout",
    "Claymation",
    "Low-Poly 3D",
    "Voxel",
    "Comic Book",
    "Sketch",
    "Chibi",
    "Cyberpunk",
    "Steampunk",
    "Dark Fantasy",
    "Fairy-Tale Fantasy",
    "Photorealistic",
    "Cinematic",
    "Surreal",
    "Vintage Film",
]

ENVIRONMENTS: list[str] = [
    "Enchanted Forest",
    "Magical Forest",
    "Ancient Forest",
    "Foggy Forest",
    "Moonlit Forest",
    "Fairy Forest",
    "Mushroom Fantasy Forest",
    "Fairy-Tale Forest",
    "Mountain Forest",
    "Rainy Forest",
    "Sunrise Forest",
    "Golden-Hour Forest",
    "Winter Forest",
    "Autumn Forest",
    "Fantasy Tropical Forest",
    "Cosmic Forest",
    "Fantasy Kingdom",
    "Dragon Fantasy",
    "Wildlife/Nature Forest",
    "Magical Wizard Forest",
]

COUNTRIES: list[str] = [
    "United States",
    "India",
    "United Kingdom",
    "Canada",
    "Australia",
    "Germany",
    "France",
    "Brazil",
    "Japan",
    "South Korea",
    "Mexico",
    "United Arab Emirates",
    "Singapore",
    "South Africa",
    "Nigeria",
]

REGIONS: list[str] = [
    "Global",
    "North America",
    "Europe",
    "Asia",
    "MENA",
    "LatAm",
    "Africa",
    "Oceania",
    "Gujarat",
    "Maharashtra",
    "Tamil Nadu",
    "California",
    "Texas",
    "Kansai",
    "Scotland",
]

LANGUAGES: list[str] = [
    "English",
    "Hindi",
    "Gujarati",
    "Bengali",
    "Tamil",
    "Telugu",
    "Marathi",
    "Japanese",
    "Korean",
    "Chinese",
    "French",
    "Spanish",
    "Portuguese",
    "German",
    "Arabic",
]

AUDIENCES: list[str] = [
    "General",
    "Gen Z",
    "Professionals",
    "Kids",
    "Parents",
    "Creators",
]

VOICES: list[str] = [
    "Original Voice",
    "AI Voice",
    "Male",
    "Female",
    "Neutral",
    "English Neutral",
    "Hindi Female",
    "Gujarati Female",
    "Bengali Female",
    "Tamil Female",
    "Telugu Female",
    "Marathi Female",
    "Japanese Female",
    "Korean Female",
    "Chinese Female",
    "French Female",
    "Spanish Male",
    "Portuguese Female",
    "German Female",
    "Arabic Female",
    "Energetic",
    "Calm",
    "Narrative",
]

VOICE_EMOTIONS: list[str] = [
    "neutral",
    "happy",
    "sad",
    "angry",
    "excited",
    "calm",
    "serious",
]

AVATARS: list[str] = [
    "No Avatar",
    "Male presenter",
    "Female presenter",
    "Business presenter",
    "Teacher",
    "News anchor",
    "Influencer",
    "Custom avatar",
]

AVATAR_EXPRESSIONS: list[str] = [
    "",
    "neutral",
    "confident",
    "warm",
    "serious",
    "friendly",
    "excited",
]

AVATAR_GESTURES: list[str] = [
    "",
    "none",
    "subtle",
    "emphasis",
    "point",
]

MUSIC_OPTIONS: list[str] = [
    "Original Audio",
    "No Music",
    "Background Music",
    "Dramatic",
    "Cinematic",
    "Funny",
    "Energetic",
    "Emotional",
    "Educational",
]

CAPTION_STYLES: list[str] = [
    "Platform Safe",
    "Minimal",
    "Pop",
    "Kinetic",
    "High Contrast",
    "TikTok",
    "Shorts",
    "Reels",
    "Podcast",
    "Gaming",
    "Educational",
]

REFRAME_ASPECTS: list[str] = [
    "Auto",
    "9:16",
    "1:1",
    "4:5",
]

HUMOR_STYLES: list[str] = [
    "None",
    "Dry",
    "Slapstick",
    "Sarcastic",
    "Wholesome",
    "Cultural",
]

# Display label → VideoJobConfig.humor_adaptation value
HUMOR_ADAPTATION_OPTIONS: list[tuple[str, str]] = [
    ("No Humor Adaptation", "none"),
    ("Original Humor", "original"),
    ("Localized Humor", "localized"),
    ("Regional Humor", "regional"),
]

HUMOR_ADAPTATION_LABELS: list[str] = [label for label, _ in HUMOR_ADAPTATION_OPTIONS]
HUMOR_ADAPTATION_LABEL_TO_VALUE: dict[str, str] = {
    label: value for label, value in HUMOR_ADAPTATION_OPTIONS
}

PLATFORMS: list[str] = [
    "Instagram",
    "Instagram Reels",
    "Facebook",
    "YouTube",
    "YouTube Shorts",
    "TikTok",
    "X",
    "LinkedIn",
    "Pinterest",
    "Snapchat",
    "Reddit",
]

TARGET_CLIP_DURATIONS: list[int] = [30, 60, 90, 180]

SHORT_DURATION_OPTIONS: list[int] = [30, 60, 90, 180]

THUMBNAIL_PLATFORMS: list[str] = [
    "Same as platform",
    "YouTube",
    "Instagram",
    "Facebook",
    "TikTok",
]

SEO_PLATFORMS: list[str] = [
    "Same as platform",
    "YouTube",
    "Instagram",
    "Facebook",
    "TikTok",
    "LinkedIn",
    "Pinterest",
]

REPURPOSE_SOURCES: list[str] = [
    "Auto",
    "Video",
    "Podcast",
    "Article",
    "Transcript",
]

# (field_key, display_label) for FeatureFlags
FEATURE_TOGGLE_DEFS: list[tuple[str, str]] = [
    ("smart_clip_detection", "Smart Clip Detection"),
    ("viral_moments", "Viral Moments"),
    ("funny_moments", "Funny Moments"),
    ("emotional_moments", "Emotional Moments"),
    ("educational_moments", "Educational Moments"),
    ("surprise_moments", "Surprise Moments"),
    ("important_moments", "Important Moments"),
    ("reaction_moments", "Reaction Moments"),
    ("inspirational_moments", "Inspirational Moments"),
    ("cinematic_moments", "Cinematic Moments"),
    ("expert_insights", "Expert Insights"),
    ("best_quotes", "Best Quotes"),
    ("b_roll", "B-Roll"),
    ("image_generation", "Image Generation"),
    ("storyboard", "Storyboard"),
    ("character", "Character Management"),
    ("camera", "Camera Planning"),
    ("director", "Director"),
    ("motion_graphics", "Motion Graphics"),
    ("documentary", "Documentary"),
    ("podcast_clips", "Podcast Clips"),
    ("research", "Research"),
    ("supervisor_crew", "Supervisor Crew"),
    ("video_generation", "Video Generation"),
    ("captions", "Captions"),
    ("voice", "Voice"),
    ("music", "Music"),
    ("avatar", "Avatar"),
    ("thumbnail", "Thumbnail"),
    ("seo", "SEO / Metadata"),
    ("brand", "Brand Kit"),
    ("trend", "Trend Detection"),
    ("repurpose", "Content Repurposing"),
    ("content_calendar", "Content Calendar"),
    ("analytics", "Analytics Prediction"),
    ("cultural_adaptation", "Cultural Adaptation"),
    ("regional_humor", "Regional Humor"),
    ("smart_reframing", "Smart Reframing"),
    ("platform_optimization", "Platform Optimization"),
    ("multi_shorts_export", "Multi Shorts Export"),
]

SOURCE_OPTIONS: list[str] = [
    "YouTube URL",
    "Upload Video / Audio",
    "Idea / Script",
]

SOURCE_LABEL_TO_TYPE: dict[str, str] = {
    "YouTube URL": "youtube",
    "Upload Video / Audio": "upload",
    "Idea / Script": "script",
}

# Separate idea option uses SourceType.IDEA (still script-ingest)
SOURCE_OPTIONS_WITH_IDEA: list[str] = [
    "YouTube URL",
    "Upload Video / Audio",
    "Idea brief",
    "Text / Script",
]

SOURCE_LABEL_TO_TYPE_FULL: dict[str, str] = {
    "YouTube URL": "youtube",
    "Upload Video / Audio": "upload",
    "Idea brief": "idea",
    "Text / Script": "script",
}

ALLOWED_UPLOAD_TYPES: list[str] = [
    "mp4",
    "mov",
    "avi",
    "mkv",
    "webm",
    "mp3",
    "wav",
    "m4a",
    "flac",
]

OUTPUT_MODES: list[str] = [
    "Animated Podcast",
    "Funny Podcast",
    "Simple Podcast",
    "Rewrite + Keep Original Video",
    "Voice Transformation",
    "Scene Transformation",
    "Full AI Transformation",
]

