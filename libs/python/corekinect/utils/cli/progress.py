def progress_bar(progress, total, message="") -> tuple:
    """
    Generates a progress bar string and the percentage completed.
    """
    bar_length = 60
    percent = (progress / total) * 100
    percent = min(percent, 100)  # Cap at 100%
    filled_length = int(bar_length * percent // 100)
    bar = "[" + "=" * filled_length + " " * (bar_length - filled_length) + f"] {percent:.1f}%\t\t{message}"

    return bar, percent
