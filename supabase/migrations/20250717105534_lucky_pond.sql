-- สร้างฐานข้อมูล
CREATE DATABASE IF NOT EXISTS project_bin;
USE project_bin;

-- ตารางผู้ใช้งาน
CREATE TABLE IF NOT EXISTS tbl_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    firstname VARCHAR(100) NOT NULL,
    lastname VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('root_admin', 'administrator', 'moderator', 'member', 'viewer') DEFAULT 'member',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตารางหมวดหมู่
CREATE TABLE IF NOT EXISTS tbl_category (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id VARCHAR(50) UNIQUE NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ตารางสินค้า
CREATE TABLE IF NOT EXISTS tbl_products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    products_id VARCHAR(50) UNIQUE NOT NULL,
    products_name VARCHAR(100) NOT NULL,
    stock INT DEFAULT 0,
    price DECIMAL(10,2) DEFAULT 0.00,
    category_id VARCHAR(50),
    description TEXT,
    barcode_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES tbl_category(category_id) ON DELETE SET NULL
);

-- ตารางคำสั่งซื้อ
CREATE TABLE IF NOT EXISTS tbl_order (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    products_id VARCHAR(50),
    products_name VARCHAR(100),
    barcode_id VARCHAR(50),
    quantity INT DEFAULT 1,
    disquantity INT DEFAULT 0,
    email VARCHAR(100),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (products_id) REFERENCES tbl_products(products_id) ON DELETE CASCADE,
    FOREIGN KEY (email) REFERENCES tbl_users(email) ON DELETE CASCADE
);

-- เพิ่มข้อมูลผู้ใช้งานตัวอย่าง
INSERT INTO tbl_users (firstname, lastname, email, password, role) VALUES
('Super', 'Admin', 'admin@example.com', 'admin123', 'root_admin'),
('John', 'Manager', 'manager@example.com', 'manager123', 'administrator'),
('Jane', 'Moderator', 'moderator@example.com', 'moderator123', 'moderator'),
('Mike', 'Member', 'member@example.com', 'member123', 'member'),
('Sarah', 'Viewer', 'viewer@example.com', 'viewer123', 'viewer');

-- เพิ่มข้อมูลหมวดหมู่ตัวอย่าง
INSERT INTO tbl_category (category_id, category_name) VALUES
('CAT001', 'Electronics'),
('CAT002', 'Clothing'),
('CAT003', 'Books'),
('CAT004', 'Food & Beverages'),
('CAT005', 'Home & Garden');

-- เพิ่มข้อมูลสินค้าตัวอย่าง
INSERT INTO tbl_products (products_id, products_name, stock, price, category_id, description, barcode_id) VALUES
('PROD001', 'Laptop Dell XPS 13', 50, 35990.00, 'CAT001', 'High-performance laptop with Intel i7 processor', 'BC001'),
('PROD002', 'iPhone 15 Pro', 30, 39900.00, 'CAT001', 'Latest iPhone with advanced camera system', 'BC002'),
('PROD003', 'Cotton T-Shirt', 100, 299.00, 'CAT002', 'Comfortable cotton t-shirt in various colors', 'BC003'),
('PROD004', 'Programming Book', 25, 890.00, 'CAT003', 'Learn programming with Python', 'BC004'),
('PROD005', 'Organic Coffee', 75, 350.00, 'CAT004', 'Premium organic coffee beans', 'BC005');

-- เพิ่มข้อมูลคำสั่งซื้อตัวอย่าง
INSERT INTO tbl_order (order_id, products_id, products_name, barcode_id, quantity, disquantity, email) VALUES
('ORD001', 'PROD001', 'Laptop Dell XPS 13', 'BC001', 2, 48, 'member@example.com'),
('ORD002', 'PROD003', 'Cotton T-Shirt', 'BC003', 5, 95, 'member@example.com'),
('ORD003', 'PROD005', 'Organic Coffee', 'BC005', 10, 65, 'viewer@example.com');

-- อัปเดตสต็อกสินค้าตามคำสั่งซื้อ
UPDATE tbl_products SET stock = 48 WHERE products_id = 'PROD001';
UPDATE tbl_products SET stock = 95 WHERE products_id = 'PROD003';
UPDATE tbl_products SET stock = 65 WHERE products_id = 'PROD005';