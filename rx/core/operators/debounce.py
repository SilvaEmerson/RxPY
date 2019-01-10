from typing import Callable, Union, Any
from datetime import timedelta

from rx.core.typing import Disposable
from rx.core import AnonymousObservable, Observable
from rx.disposables import CompositeDisposable, SingleAssignmentDisposable, SerialDisposable
from rx.concurrency import timeout_scheduler


def _debounce(duetime: Union[int, timedelta]) -> Callable[[Observable], Observable]:
    """Ignores values from an observable sequence which are followed by
    another value before duetime.

    Example:
        >>> res = debounce(5000)(source) # 5 seconds

    Args:
        duetime: Duration of the throttle period for each value
        (specified as an integer denoting milliseconds).

    Returns:
        An operator function that takes the source observable and
        returns the debounced observable sequence.
    """

    def debounce(source: Observable) -> Observable:
        def subscribe(observer, scheduler=None) -> Disposable:
            scheduler = scheduler or timeout_scheduler
            cancelable = SerialDisposable()
            has_value = [False]
            value = [None]
            _id = [0]

            def on_next(x: Any) -> None:
                has_value[0] = True
                value[0] = x
                _id[0] += 1
                current_id = _id[0]
                d = SingleAssignmentDisposable()
                cancelable.disposable = d

                def action(scheduler, state=None) -> None:
                    if has_value[0] and _id[0] == current_id:
                        observer.on_next(value[0])
                    has_value[0] = False

                d.disposable = scheduler.schedule_relative(duetime, action)

            def on_error(exception: Exception) -> None:
                cancelable.dispose()
                observer.on_error(exception)
                has_value[0] = False
                _id[0] += 1

            def on_completed() -> None:
                cancelable.dispose()
                if has_value[0]:
                    observer.on_next(value[0])

                observer.on_completed()
                has_value[0] = False
                _id[0] += 1

            subscription = source.subscribe_(on_next, on_error, on_completed, scheduler=scheduler)
            return CompositeDisposable(subscription, cancelable)
        return AnonymousObservable(subscribe)
    return debounce


def _throttle_with_mapper(throttle_duration_mapper: Callable[[Any], Observable]) -> Callable[[Observable], Observable]:
    def throttle_with_mapper(source: Observable) -> Observable:
        """Partially applied throttle_with_mapper operator.

        Ignores values from an observable sequence which are followed by
        another value within a computed throttle duration.

        Example:
            >>> obs = throttle_with_mapper(source)

        Args:
            source: The observable source to throttle.

        Returns:
            The throttled observable sequence.
        """
        def subscribe(observer, scheduler=None) -> Disposable:
            cancelable = SerialDisposable()
            has_value = [False]
            value = [None]
            _id = [0]

            def on_next(x):
                throttle = None
                try:
                    throttle = throttle_duration_mapper(x)
                except Exception as e:  # pylint: disable=broad-except
                    observer.on_error(e)
                    return

                has_value[0] = True
                value[0] = x
                _id[0] += 1
                current_id = _id[0]
                d = SingleAssignmentDisposable()
                cancelable.disposable = d

                def on_next(x: Any) -> None:
                    if has_value[0] and _id[0] == current_id:
                        observer.on_next(value[0])

                    has_value[0] = False
                    d.dispose()

                def on_completed() -> None:
                    if has_value[0] and _id[0] == current_id:
                        observer.on_next(value[0])

                    has_value[0] = False
                    d.dispose()

                d.disposable = throttle.subscribe_(on_next, observer.on_error, on_completed, scheduler=scheduler)

            def on_error(e) -> None:
                cancelable.dispose()
                observer.on_error(e)
                has_value[0] = False
                _id[0] += 1

            def on_completed() -> None:
                cancelable.dispose()
                if has_value[0]:
                    observer.on_next(value[0])

                observer.on_completed()
                has_value[0] = False
                _id[0] += 1

            subscription = source.subscribe_(on_next, on_error, on_completed, scheduler=scheduler)
            return CompositeDisposable(subscription, cancelable)
        return AnonymousObservable(subscribe)
    return throttle_with_mapper