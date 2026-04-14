import subprocess


def ffmpegEncode(input_path, output_path):
    command = [
        'ffmpeg', '-i', input_path,
        '-c', 'copy', '-bsf:a',
        'aac_adtstoasc', '-movflags',
        '+faststart', output_path
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print(result.stderr)
        return False

    return True
