import asyncio
from asyncio.subprocess import Process


async def monitor_process(process: Process, label: str):
    """Wait and monitor the process given as input printing the stdout and
    stderr content

    Args:
        process (Process): the process to wait and monitor
        label (str): the label identifying the process
    """
    stdout_read = asyncio.create_task(process.stdout.readline())
    stderr_read = asyncio.create_task(process.stderr.readline())
    tasks = [stdout_read, stderr_read]
    while tasks:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )
        tasks = list(pending)
        for d in done:
            if d.result():
                print(f'[{label}]: {d.result().decode()[:-1]}')
                if d == stdout_read:
                    stdout_read = asyncio.create_task(
                        process.stdout.readline())
                    tasks.append(stdout_read)
                else:
                    stderr_read = asyncio.create_task(
                        process.stderr.readline())
                    tasks.append(stderr_read)
