import asyncio
import functools
import multiprocessing
import socket
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from kombu import Connection, Exchange, Queue, Message

exchange_start = Exchange("start-exchange", "direct")
queue_start = Queue(name="start", exchange=exchange_start, routing_key="start")
exchange_cancel = Exchange("cancel-exchange", "direct")
queue_cancel = Queue(exchange=exchange_cancel, routing_key="cancel")

work_in_progress = None
event_manager = multiprocessing.Manager()

async def main():
    global handler

    async_queue = asyncio.Queue()

    def on_message(message: Message):
        async_queue.put_nowait(message)

    with Connection("amqp://rabbitmq:rabbitmq@localhost:5672") as connection:
        with connection.Consumer([queue_start], on_message=on_message, prefetch_count=1):
            with connection.Consumer([queue_cancel], on_message=on_message, no_ack=True):
                asyncio.create_task(message_handler(async_queue))

                print("Waiting for messages")
                while True:
                    await asyncio.create_task(connection_consumer(connection))
                    await async_queue.join()

async def connection_consumer(connection: Connection):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(1) as pool:
        while True:
            try:
                await loop.run_in_executor(pool, functools.partial(connection.drain_events, timeout=3))
            except socket.timeout:
                if work_in_progress is None:
                    break

async def message_handler(async_queue: asyncio.Queue):
    global work_in_progress

    while True:
        message = await async_queue.get()

        body = message.decode()
        print(f'Got message with properties {message.delivery_info} and payload \"{body}\"')

        if body == "start":
            pool = ProcessPoolExecutor(1)
            cancel_event = event_manager.Event()
            loop = asyncio.get_event_loop()
            work_in_progress = loop.run_in_executor(pool, main_task, cancel_event)

            def on_done(_):
                global work_in_progress

                pool.shutdown()
                message.ack()
                work_in_progress = None
                print("Message acked")
            
            work_in_progress.add_done_callback(on_done)
            print("Task created")
        
        elif body == "cancel":
            cancel_event.set()
            print("Initiated task cancellation")

        async_queue.task_done()

def main_task(cancel_event):
    import time

    print("[subprocess] Task started")
    passed_secs = 0
    while cancel_event.is_set() == False and passed_secs < 10:
        time.sleep(1)
        passed_secs += 1
    
    if cancel_event.is_set():
        print("[subprocess] Task cancelled")
    else:
        print("[subprocess] Task finished normally")

if __name__ == "__main__":
    asyncio.run(main())