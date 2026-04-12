import random
from typing import List, Dict, Callable

def generate_employee_data(rng: random.Random) -> str:
    depts = ["Engineering", "Marketing", "Sales", "HR"]
    names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Heidi", "Ivan", "Judy"]
    sql = []
    for i in range(1, 101): # 100 rows
        name = rng.choice(names) + f" {i}"
        dept = rng.choice(depts)
        salary = rng.randint(50000, 150000)
        sql.append(f"INSERT INTO employees VALUES ({i}, '{name}', '{dept}', {salary});")
    return "\n".join(sql)

def generate_order_data(rng: random.Random) -> str:
    names = ["Alice", "Bob", "Carol", "Dave", "Eve"]
    statuses = ["completed", "pending", "cancelled"]
    sql = []
    for i in range(1, 151): # 150 rows
        name = rng.choice(names)
        amt = round(rng.uniform(10.0, 500.0), 2)
        status = rng.choice(statuses)
        sql.append(f"INSERT INTO orders VALUES ({i}, '{name}', {amt}, '{status}');")
    return "\n".join(sql)

def generate_customer_purchase_data(rng: random.Random) -> str:
    names = ["Alice", "Bob", "Carol", "Dave", "Eve"]
    products = ["Laptop", "Mouse", "Keyboard", "Monitor", "Headphones"]
    sql = []
    for i in range(1, 51):
        sql.append(f"INSERT INTO customers VALUES ({i}, '{names[i%5]} {i}', '{names[i%5].lower()}{i}@example.com');")
    for i in range(1, 201):
        cust_id = rng.randint(1, 50)
        prod = rng.choice(products)
        amt = round(rng.uniform(20.0, 1500.0), 2)
        sql.append(f"INSERT INTO purchases VALUES ({i}, {cust_id}, '{prod}', {amt});")
    return "\n".join(sql)

def generate_sales_data(rng: random.Random) -> str:
    regions = ["North", "South", "East", "West"]
    products = ["Widget", "Gadget", "Doodad"]
    sql = []
    for i in range(1, 301):
        region = rng.choice(regions)
        prod = rng.choice(products)
        rev = round(rng.uniform(100.0, 1000.0), 2)
        sql.append(f"INSERT INTO sales VALUES ({i}, '{region}', '{prod}', {rev});")
    return "\n".join(sql)

def generate_employee_dept_data(rng: random.Random) -> str:
    sql = []
    depts = [("Engineering", 500000), ("Marketing", 200000), ("HR", 150000), ("Sales", 300000), ("Legal", 250000)]
    for i, (name, budget) in enumerate(depts, 1):
        sql.append(f"INSERT INTO departments VALUES ({i}, '{name}', {budget});")
    
    names = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Heidi"]
    for i in range(1, 251):
        dept_id = rng.randint(1, 5)
        name = rng.choice(names) + f" {i}"
        salary = rng.randint(50000, 130000)
        date = f"202{rng.randint(0,3)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
        sql.append(f"INSERT INTO employees VALUES ({i}, '{name}', {dept_id}, {salary}, '{date}');")
    return "\n".join(sql)

def generate_ecommerce_data(rng: random.Random) -> str:
    sql = []
    # 7 Tables: Users, Categories, Products, Orders, Order_Items, Reviews, Shipping
    for i in range(1, 101):
        sql.append(f"INSERT INTO users VALUES ({i}, 'user_{i}', 'user{i}@test.com', '2023-01-01');")
    
    cats = ["Electronics", "Books", "Home", "Fashion", "Toys"]
    for i, cat in enumerate(cats, 1):
        sql.append(f"INSERT INTO categories VALUES ({i}, '{cat}');")
    
    for i in range(1, 51):
        cat_id = rng.randint(1, 5)
        sql.append(f"INSERT INTO products VALUES ({i}, 'product_{i}', {cat_id}, {round(rng.uniform(10, 1000), 2)});")
    
    for i in range(1, 301):
        user_id = rng.randint(1, 100)
        sql.append(f"INSERT INTO orders VALUES ({i}, {user_id}, '2023-01-{rng.randint(1,30):02d}', 'delivered');")
        for j in range(1, rng.randint(2, 5)):
            prod_id = rng.randint(1, 50)
            sql.append(f"INSERT INTO order_items VALUES ({i*10+j}, {i}, {prod_id}, {rng.randint(1,3)}, {round(rng.uniform(10, 1000), 2)});")
    
    return "\n".join(sql)

TASKS = [
    {
        "id": "fix_syntax_simple",
        "difficulty": "easy",
        "max_steps": 5,
        "schema_ddl": """
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                salary REAL NOT NULL
            )
        """,
        "data_factory": generate_employee_data,
        "broken_query": "SELECT name department, salary FROM employees WHERE department = 'Engineering'",
        "ground_truth_query": "SELECT name, department, salary FROM employees WHERE department = 'Engineering'",
        "expected_description": "Retrieve the name, department, and salary for all employees in the 'Engineering' department. The current query fails to return individual columns correctly.",
    },
    {
        "id": "fix_table_name",
        "difficulty": "easy",
        "max_steps": 5,
        "schema_ddl": "CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_name TEXT NOT NULL, total_amount REAL NOT NULL, status TEXT NOT NULL)",
        "data_factory": generate_order_data,
        "broken_query": "SELECT customer_name, total_amount FROM order WHERE status = 'completed'",
        "ground_truth_query": "SELECT customer_name, total_amount FROM orders WHERE status = 'completed'",
        "expected_description": "List the customer names and total amounts for all orders that have a status of 'completed'. Ensure the source table is referenced correctly.",
    },
    {
        "id": "fix_join_logic",
        "difficulty": "medium",
        "max_steps": 8,
        "schema_ddl": """
            CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, customer_name TEXT NOT NULL, email TEXT NOT NULL);
            CREATE TABLE purchases (purchase_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, product TEXT NOT NULL, amount REAL NOT NULL)
        """,
        "data_factory": generate_customer_purchase_data,
        "broken_query": "SELECT c.customer_name, p.product, p.amount FROM customers c JOIN purchases p ON c.customer_id = p.purchase_id WHERE p.amount > 500",
        "ground_truth_query": "SELECT c.customer_name, p.product, p.amount FROM customers c JOIN purchases p ON c.customer_id = p.customer_id WHERE p.amount > 500",
        "expected_description": "Find the names of customers and the details of their purchases where the purchase amount exceeds 500. Ensure the relationship between customers and purchases is established correctly.",
    },
    {
        "id": "fix_aggregate_logic",
        "difficulty": "medium",
        "max_steps": 8,
        "schema_ddl": "CREATE TABLE sales (sale_id INTEGER PRIMARY KEY, region TEXT NOT NULL, product TEXT NOT NULL, revenue REAL NOT NULL)",
        "data_factory": generate_sales_data,
        "broken_query": "SELECT region, SUM(revenue) as total_revenue FROM sales GROUP BY product HAVING SUM(revenue) > 2000",
        "ground_truth_query": "SELECT region, SUM(revenue) as total_revenue FROM sales GROUP BY region HAVING SUM(revenue) > 2000",
        "expected_description": "Calculate the total revenue for each region, returning only those regions where the total revenue is greater than 2000.",
    },
    {
        "id": "multi_constraint_query",
        "difficulty": "hard",
        "max_steps": 10,
        "schema_ddl": """
            CREATE TABLE employees (emp_id INTEGER PRIMARY KEY, emp_name TEXT NOT NULL, dept_id INTEGER NOT NULL, salary REAL NOT NULL, hire_date TEXT NOT NULL);
            CREATE TABLE departments (dept_id INTEGER PRIMARY KEY, dept_name TEXT NOT NULL, budget REAL NOT NULL)
        """,
        "data_factory": generate_employee_dept_data,
        "broken_query": "SELECT d.dept_name, COUNT(*) as headcount, AVG(e.salary) as avg_salary FROM departments d LEFT JOIN employees e ON d.dept_id = e.dept_id GROUP BY d.dept_name, e.salary HAVING COUNT(*) > 5 AND AVG(salary) > 80000 ORDER BY avg_salary",
        "ground_truth_query": "SELECT d.dept_name, COUNT(*) as headcount, AVG(e.salary) as avg_salary FROM departments d INNER JOIN employees e ON d.dept_id = e.dept_id GROUP BY d.dept_name HAVING COUNT(*) > 5 AND AVG(e.salary) > 80000 ORDER BY avg_salary DESC",
        "expected_description": "For each department with more than 5 employees and an average salary above 80000, retrieve the department name, headcount, and average salary. Results should be ordered by average salary from highest to lowest.",
    },
    {
        "id": "ecommerce_supply_chain",
        "difficulty": "hard",
        "max_steps": 12,
        "schema_ddl": """
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, email TEXT, joined_at TEXT);
            CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER, price REAL);
            CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, order_date TEXT, status TEXT);
            CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER, quantity INTEGER, price_at_purchase REAL);
        """,
        "data_factory": generate_ecommerce_data,
        "broken_query": """
            SELECT u.username, SUM(oi.quantity * oi.price_at_purchase) as total_spent
            FROM users u
            JOIN orders o ON u.id = o.user_id
            JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'delivered'
            GROUP BY u.id
            HAVING total_spent > 1000
            ORDER BY total_spent
        """,
        "ground_truth_query": """
            SELECT u.username, SUM(oi.quantity * oi.price_at_purchase) as total_spent
            FROM users u
            JOIN orders o ON u.id = o.user_id
            JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'delivered'
            GROUP BY u.username
            HAVING SUM(oi.quantity * oi.price_at_purchase) > 1000
            ORDER BY total_spent DESC
        """,
        "expected_description": "List the usernames of all customers who have spent a total of more than 1000 on 'delivered' orders, along with their total spend, ordered by spend in descending order.",
    }
]

TASK_INDEX = {task["id"]: task for task in TASKS}