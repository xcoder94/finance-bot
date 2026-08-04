SHARED_WALLET_LIMIT = 10
PERSONAL_WALLET_LIMIT = 5
PARENT_CATEGORY_LIMIT = 8
SUBCATEGORY_LIMIT = 8
ENTITY_NAME_MAX = 30

LIMIT_SHARED_WALLETS = (
    "Больше 10 общих кошельков создать нельзя. Удалите ненужный — место освободится."
)
LIMIT_PERSONAL_WALLETS = (
    "Больше 5 личных кошельков создать нельзя. Удалите ненужный — место освободится."
)
LIMIT_EXPENSE_PARENTS = (
    "Больше 8 категорий расходов создать нельзя. Удалите ненужную — место освободится."
)
LIMIT_INCOME_CATEGORIES = (
    "Больше 8 категорий доходов создать нельзя. Удалите ненужную — место освободится."
)


def limit_subcategories(parent_name: str) -> str:
    return (
        f"В категории «{parent_name}» уже 8 подкатегорий — это предел. "
        "Удалите ненужную, чтобы добавить новую."
    )


def normalize_entity_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValueError("name must not be empty")
    if len(normalized) > ENTITY_NAME_MAX:
        raise ValueError(f"name must be at most {ENTITY_NAME_MAX} characters")
    return normalized
