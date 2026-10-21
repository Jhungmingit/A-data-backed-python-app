import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

# connecting to the engine
def get_engine():
    """Create and return a SQLAlchemy engine from DATABASE_URL."""
    url = os.getenv("DATABASE_URL")
    
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
    engine = create_engine(url)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        print("Could not connect to the database. Is the container running?")
        raise
    return engine


def store_report(engine):
    """Print counts, the catalog, and the top 3 customers."""
    with engine.connect() as conn:

        # total number of users, products, and orders;
        users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        products = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
        orders = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()

        print("=== Store Dashboard ===")
        print(f"Users: {users} | Products: {products} | Orders: {orders}")

        # the catalog: each product's name, price, and stock;
        rows = conn.execute(text("SELECT name, price, stock FROM products ORDER BY name")).all()
        print("\nCatalog:")
        for name, price, stock in rows:
            print(f"{name:<30} ${price:>9.2f} (stock {stock})")

        # the top 3 customers by total items ordered (a join + GROUP BY + ORDER BY + LIMIT).
        top = conn.execute(text("""
            SELECT u.email, SUM(o.quantity) AS items
            FROM orders o
            JOIN users u ON u.id = o.user_id
            GROUP BY u.email
            ORDER BY items DESC, u.email
            LIMIT 3
        """)).all()

        print("\nTop customers:")

        #if in any case, said items are plural or singular this for loop will handle it
        for email, items in top:
            label = "item" if items == 1 else "items"
            print(f"{email} - {items} {label}")

def add_product(engine, name, category, price, stock):
    """INSERT a product and return its new id."""
    with engine.begin() as conn:   
        result = conn.execute(text("""
             INSERT INTO products (name, category, price, stock)
             VALUES (:name, :category, :price, :stock)
             RETURNING id
        """), {"name": name, "category": category, "price": price, "stock": stock})
        return result.scalar()   
        

def place_order(engine, email, product_name, quantity):
    """Create an order and decrement stock in one transaction."""
    with engine.begin() as conn:  
        
        # Find the user by email 
        result = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email}
        )    
        row = result.fetchone()

        if row is None:
            raise ValueError("User not found")

        user_id = row[0]

        print("User ID:", user_id)

        result = conn.execute(
           
            # Find the product 
            text("SELECT id, stock " \
            "FROM products " \
            "WHERE name = :product_name FOR UPDATE"),  # FOR UPDATE Locks the selected row until the transaction finishes which helps prevent concurrent orders from reducing stock incorrectly
            {"product_name": product_name}
        )
        # fetches one column of a row
        row = result.fetchone()

        if row is None:
            raise ValueError("Product not found")

        product_id = row[0]
        stock = row[1]

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")

        if stock < quantity:
            raise ValueError("Not enough stock")
      
        # inserting orders into the database
        conn.execute(
            text("""
                INSERT INTO orders (user_id, product_id, quantity)
                VALUES (:user_id, :product_id, :quantity)
            """),
            {
                "user_id": user_id,
                "product_id": product_id,
                "quantity": quantity
            }
        )
        
        # Decrease stock 
        conn.execute(
            text("""
                UPDATE products
                SET stock = stock - :quantity 
                WHERE id = :product_id 
            """),
            {
                "quantity": quantity,
                "product_id": product_id
            }
        )

        print("Order placed successfully!")


def main():
    engine = get_engine()
    store_report(engine)

    while True:
        print("\n=== Jhung min's Store Dashboard ===")
        print("1. View store report")
        print("2. Add a product")
        print("3. Place an order")
        print("4. Exit")

        choice = input("Choose an option: ")
       
        # View store report 
        if choice == "1":
            store_report(engine)
        
        # Add product 
        elif choice == "2":
            name = input("Product name: ")
            category = input("Category: ")
            price = float(input("Price: "))
            stock = int(input("Stock: "))

            product_id = add_product(engine, name, category, price, stock)
            print(f"Product added successfully! ID: {product_id}")
       
        # Place an order 
        elif choice == "3":
            email = input("email: ")
            product_name = input("Product name: ")
            quantity = int(input("Quantity: "))

            try:
                place_order(engine, email, product_name, quantity)
            except ValueError as e:
                print(f"Order failed: {e}")    
       
        # Exit program 
        elif choice == "4":
            print("Exiting...")
            break

if __name__ == "__main__":
    main()
