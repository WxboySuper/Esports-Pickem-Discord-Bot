import logging
from typing import List, Optional, Type, Any
from sqlmodel import Session
from src.models import (
    User,
    Contest,
    Match,
    Pick,
    Result,
    Team,
)

logger = logging.getLogger(__name__)

class _DBHelpers:
    """Grouped synchronous DB helper operations to improve cohesion.

    Module-level wrapper functions delegate to these methods so external
    callers keep the same API while internal functionality is grouped.
    """

    @staticmethod
    def save_and_refresh(session: Session, obj: Any) -> Any:
        """
        Persist an ORM object to the database and refresh its state
        from the session.

        Parameters:
            obj (Any): ORM model instance to add, commit, and refresh
                in the given session.

        Returns:
            Any: The same `obj` instance after commit and session
                refresh, reflecting persisted database state.
        """
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj

    @staticmethod
    def save_all_and_refresh(session: Session, objs: List[Any]) -> List[Any]:
        """
        Persist multiple ORM objects to the database and refresh them
        from the session.

        Parameters:
            objs (List[Any]): Iterable of mapped ORM instances to add
                and persist.

        Returns:
            List[Any]: The same list of instances after being
                refreshed with the database state.
        """
        session.add_all(objs)
        session.commit()
        for o in objs:
            session.refresh(o)
        return objs

    @staticmethod
    def delete_and_commit(session: Session, obj: Any) -> None:
        """
        Delete an ORM mapped instance from the provided session and
        commit the transaction.

        Parameters:
            session (Session): SQLAlchemy session used to perform the
                deletion and commit.
            obj (Any): ORM-mapped instance to be removed from the
                database.
        """
        session.delete(obj)
        session.commit()

    @staticmethod
    def create_model(session: Session, model: Type[Any], **kwargs) -> Any:
        """
        Create and persist a new instance of the given model using
        the provided field values.

        Parameters:
            model (Type[Any]): ORM model class to instantiate.
            **kwargs: Field values passed to the model constructor.

        Returns:
            Any: The newly created and refreshed model instance.
        """
        obj = model(**kwargs)
        _DBHelpers.save_and_refresh(session, obj)
        return obj

    @staticmethod
    def get_model_by_id(
        session: Session, model: Type[Any], obj_id: int
    ) -> Optional[Any]:
        """
        Retrieve a mapped model instance by its primary key.

        Parameters:
            model (Type[Any]): ORM model class to query.
            obj_id (int): Primary key of the desired object.

        Returns:
            The model instance if found, `None` otherwise.
        """
        return session.get(model, obj_id)

    @staticmethod
    def update_model_fields(
        session: Session, model: Type[Any], obj_id: int, **fields
    ) -> Optional[Any]:
        """
        Update specified attributes on a model instance identified by
        its primary key.

        Only attributes provided in `**fields` whose values are not
        `None` are applied. The instance is persisted and refreshed
        before being returned.

        Parameters:
            model (Type[Any]): ORM model class of the object to
                update.
            obj_id (int): Primary key of the object to update.
            **fields: Attribute names and their new values; attributes
                with value `None` are ignored.

        Returns:
            Optional[Any]: The updated and refreshed model instance,
                or `None` if no object with `obj_id` exists.
        """
        obj = session.get(model, obj_id)
        if not obj:
            return None
        for k, v in fields.items():
            if v is not None:
                setattr(obj, k, v)
        _DBHelpers.save_and_refresh(session, obj)
        return obj

    @staticmethod
    def delete_model_by_id(
        session: Session, model: Type[Any], obj_id: int
    ) -> bool:
        """
        Delete the database record of the given model with the
        specified primary key if it exists.

        Parameters:
            model (Type[Any]): ORM model class to delete from.
            obj_id (int): Primary key of the object to delete.

        Returns:
            bool: `True` if the object was found and deleted, `False`
                otherwise.
        """
        obj = session.get(model, obj_id)
        if not obj:
            return False
        _DBHelpers.delete_and_commit(session, obj)
        return True


# Backwards-compatible thin wrappers (preserve module API)
def _save_and_refresh(session: Session, obj: Any) -> Any:
    """
    Persist the given ORM object, commit the transaction, refresh its
    state from the database, and return it.

    Returns:
        The same object after being persisted and refreshed.
    """
    return _DBHelpers.save_and_refresh(session, obj)


def _save_all_and_refresh(session: Session, objs: List[Any]) -> List[Any]:
    """
    Persist multiple ORM objects in the database, commit the
    transaction, and refresh each instance.

    Parameters:
        objs (List[Any]): Iterable of ORM instances to be added and
            refreshed.

    Returns:
        List[Any]: The provided objects after being committed and
            refreshed.
    """
    return _DBHelpers.save_all_and_refresh(session, objs)


def _delete_and_commit(session: Session, obj: Any) -> None:
    """
    Delete a mapped ORM object from the given session and commit the
    transaction.

    Parameters:
        session (Session): Active SQLAlchemy session used for the
            operation.
        obj (Any): Mapped ORM instance to remove from the database.
    """
    return _DBHelpers.delete_and_commit(session, obj)


def _create_model(session: Session, model: Type[Any], **kwargs) -> Any:
    """
    Create and persist a new instance of the given model using the
    provided field values.

    Parameters:
        session (Session): Database session used to persist the
            instance.
        model (Type[Any]): ORM model class to instantiate.
        **kwargs: Field values passed to the model constructor.

    Returns:
        Any: The newly created and refreshed model instance.
    """
    return _DBHelpers.create_model(session, model, **kwargs)


def _get_model_by_id(
    session: Session,
    model: Type[Any],
    obj_id: int,
) -> Optional[Any]:
    """
    Retrieve a model instance by its primary key.

    Parameters:
        model (Type[Any]): ORM model class to query.
        obj_id (int): Primary key of the desired record.

    Returns:
        The model instance if found, otherwise None.
    """
    return _DBHelpers.get_model_by_id(session, model, obj_id)


def _update_model_fields(
    session: Session,
    model: Type[Any],
    obj_id: int,
    **fields,
) -> Optional[Any]:
    """
    Update the specified fields on a model instance identified by its
    primary key and persist the changes.

    Parameters:
        model (Type[Any]): ORM model class of the object to update.
        obj_id (int): Primary key of the object to update.
        **fields: Field names and their new values; only keys with
            non-None values are applied.

    Returns:
        Any | None: The updated model instance after persistence, or
            `None` if no object with `obj_id` was found.
    """
    return _DBHelpers.update_model_fields(session, model, obj_id, **fields)


def _delete_model_by_id(
    session: Session,
    model: Type[Any],
    obj_id: int,
) -> bool:
    """
    Remove a single database model instance identified by its primary key.

    Parameters:
        model (Type[Any]): ORM model class to delete from.
        obj_id (int): Primary key of the object to remove.

    Returns:
        bool: `True` if an object was deleted, `False` if no matching
            object was found.
    """
    return _DBHelpers.delete_model_by_id(session, model, obj_id)
