from video.video_generator import generate_video

scenes = [
    {"text": "Welcome to our AI video generation project."},
    {"text": "Our system transforms documents into engaging videos."},
    {"text": "FFmpeg combines visuals, narration, and subtitles."},
]

try:
    output = generate_video(
        scenes,
        title="SIH 26154 Demo",
    )
    print("SUCCESS: Video generated!")
    print("Output:", output)

except Exception as error:
    print("FAILED:", error)
    raise
