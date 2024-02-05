# rabbitmq-ack-test

The demonstration of a problem in message acknowledgement by kombu package with a RabbitMQ broker.

This script aims to run a task in a sub-process and to support cancelling it.

The script uses `kombu` package which has a blocking API. To be able to consume messages from queues and handle them concurrently, we use an `asyncio` event loop.

We want the broker to balance the load on multiple instances of the script, that's why we use two queues:
* the first queue is named `start` so it is shared by all instances and the broker can distribute `start` messages in a round-robin fashion. We set `prefetch_count=1` on the associated consumer to prevent the broker to distribute a task to an already busy instance.
* the second queue has no such constraints, `cancel` messages can be safely broadcasted to every instance. We even set `no_ack=True` to enable automatic acknowledgement.

Since the task itself is blocking, we run it in a subprocess. We use an `Event` from `multiprocessing` to notify the task it was cancelled.

## Prerequisites

* Python 3.8
  * I did not test with a more recent version
* Poetry
  * Run `poetry install` to setup virtual environment and dependencies

## Steps to reproduce

I assume a RabbitMQ server runs on localhost (port=5672, user=rabbitmq, pass=rabbitmq).

* Run the script with `poetry run python -m rabbitmq_ack_test`
  * It is waiting for messages.
* Check the presence of the `start` queue and its size with `rabbitmqctl list_queues | grep start`:
  * start   0
* Publish a `start` message followed by a `cancel` one:
    ```
    rabbitmq publish routing_key=start payload=start`
    rabbitmq publish routing_key=cancel payload=cancel`
    ```
* The script shows it has taken into account both messages, the task that started has been cancelled and the message was acked.
* Check the size of the `start` queue:
  * start   1

## Expectations

Since the `start` message was acknowledged in the script, it should be removed from the queue.

## Additional observations

The problem does not occur when the task is completed normally (without cancel).