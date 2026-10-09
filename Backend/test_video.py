from video.video_generator import generate_video

scenes = [
    {
        "text": (
            "Welcome to ContentForge AI, "
            "an intelligent content transformation platform."
        )
    },
    {
        "text": (
            "Our platform transforms reports and documents "
            "into useful communication formats."
        )
    },
    {
        "text": (
            "It can generate summaries, presentations, "
            "voiceovers and videos."
        )
    },
]

video_path = generate_video(
    scenes,
    title="ContentForge AI - SIH 26154",
)

print("Final video:", video_path)
