from typing import Annotated

from fastapi import Depends

from orders.domain.repository import OrderRepository, get_repository

Repo = Annotated[OrderRepository, Depends(get_repository)]
