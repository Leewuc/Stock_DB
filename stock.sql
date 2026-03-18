create database team6;
use team6;



CREATE TABLE users (
    user_id INT PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    gender BOOLEAN NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    pwd VARCHAR(255) NOT NULL,
    birth_day DATE NOT NULL,
    phone VARCHAR(255) NOT NULL UNIQUE,
    stock_holding INT NOT NULL,
    account_no INT NOT NULL,
    stock_id VARCHAR(255) NOT NULL,
    stock_itrs_id VARCHAR(255) NOT NULL,
    INDEX (account_no),
    INDEX (stock_id),
    INDEX (stock_itrs_id)
);

CREATE TABLE accounts (
    account_no INT PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL UNIQUE,
    account_pwd VARCHAR(255) NOT NULL,
    create_date DATE NOT NULL,
    account_balance INT NOT NULL,
    account_status VARCHAR(255) NOT NULL,
    stock_holding_id INT NOT NULL,
    stock_id VARCHAR(255) NOT NULL,
    INDEX (stock_holding_id),
    INDEX (stock_id)
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT NOT NULL,
    account_id INT NOT NULL,
    stock_id VARCHAR(255) NOT NULL,
    orders_quantity INT NOT NULL,
    orders_price DECIMAL(10, 2) NOT NULL,
    orders_ordertype VARCHAR(255) NOT NULL,
    orders_dt DATETIME NOT NULL,
    INDEX (customer_id),
    INDEX (account_id),
    INDEX (stock_id)
);

CREATE TABLE stocks (
    stock_id VARCHAR(255) PRIMARY KEY,
    stock_name VARCHAR(255) NOT NULL,
    stock_code VARCHAR(255) NOT NULL UNIQUE,
    stock_listing BOOLEAN NOT NULL,
    capital INT NOT NULL,
    face_value INT NOT NULL,
    market_capital INT NOT NULL,
    transaction_amount INT NOT NULL,
    eps INT NOT NULL,
    bps INT NOT NULL,
    roe INT NOT NULL
);

CREATE TABLE stocks_holding (
    stock_holding_id INT PRIMARY KEY,
    stock_id VARCHAR(255) NOT NULL,
    current_price DECIMAL(10, 2) NOT NULL,
    INDEX (stock_id)
);

CREATE TABLE stocks_itrs (
    stock_itrs_id VARCHAR(255) PRIMARY KEY,
    stock_id VARCHAR(255) NOT NULL,
    cur_price DECIMAL(10, 2) NOT NULL,
    INDEX (stock_id)
);

CREATE TABLE trade_histories (
    trade_id INT PRIMARY KEY,
    histories_quantity INT NOT NULL,
    histories_price DECIMAL(10, 2) NOT NULL,
    trade_type VARCHAR(255) NOT NULL,
    trade_datetime DATETIME NOT NULL,
    account_no INT NOT NULL,
    customer_id INT NOT NULL,
    stock_id VARCHAR(255) NOT NULL,
    INDEX (account_no),
    INDEX (customer_id),
    INDEX (stock_id)
);

CREATE TABLE news (
    news_id INT PRIMARY KEY,
    news_title VARCHAR(255) NOT NULL,
    news_content TEXT NOT NULL,
    written_at TIMESTAMP NOT NULL,
    news_source VARCHAR(255) NOT NULL,
    news_url VARCHAR(255) NOT NULL,
    news_created_at DATETIME NOT NULL,
    news_updated_at DATETIME NOT NULL,
    stock_holding_id INT NOT NULL,
    stock_itrs_id VARCHAR(255) NOT NULL,
    stock_id VARCHAR(255) NOT NULL,
    INDEX (stock_holding_id),
    INDEX (stock_itrs_id),
    INDEX (stock_id)
);

CREATE TABLE news_comment (
    comment_id INT PRIMARY KEY,
    comment_written_at TIMESTAMP NOT NULL,
    comment_content TEXT NOT NULL,
    news_id INT NOT NULL,
    stock_id VARCHAR(255) NOT NULL,
    INDEX (news_id),
    INDEX (stock_id)
);

-- 제약 조건 추가
ALTER TABLE users
    ADD FOREIGN KEY (account_no) REFERENCES accounts(account_no),
    ADD FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),
    ADD FOREIGN KEY (stock_itrs_id) REFERENCES stocks_itrs(stock_itrs_id);

ALTER TABLE accounts
    ADD FOREIGN KEY (stock_holding_id) REFERENCES stocks_holding(stock_holding_id),
    ADD FOREIGN KEY (stock_id) REFERENCES stocks(stock_id);

ALTER TABLE orders
    ADD FOREIGN KEY (customer_id) REFERENCES users(user_id),
    ADD FOREIGN KEY (account_id) REFERENCES accounts(account_no),
    ADD FOREIGN KEY (stock_id) REFERENCES stocks(stock_id);

ALTER TABLE stocks_holding
    ADD FOREIGN KEY (stock_id) REFERENCES stocks(stock_id);

ALTER TABLE stocks_itrs
    ADD FOREIGN KEY (stock_id) REFERENCES stocks(stock_id);

ALTER TABLE trade_histories
    ADD FOREIGN KEY (account_no) REFERENCES accounts(account_no),
    ADD FOREIGN KEY (customer_id) REFERENCES users(user_id),
    ADD FOREIGN KEY (stock_id) REFERENCES stocks(stock_id);

ALTER TABLE news
    ADD FOREIGN KEY (stock_holding_id) REFERENCES stocks_holding(stock_holding_id),
    ADD FOREIGN KEY (stock_itrs_id) REFERENCES stocks_itrs(stock_itrs_id),
    ADD FOREIGN KEY (stock_id) REFERENCES stocks(stock_id);

ALTER TABLE news_comment
    ADD FOREIGN KEY (news_id) REFERENCES news(news_id),
    ADD FOREIGN KEY (stock_id) REFERENCES stocks(stock_id);


-- accounts 테이블에 더미 데이터 삽입
INSERT INTO accounts (account_no, account_id, account_pwd, create_date, account_balance, account_status, stock_holding_id, stock_id) VALUES
(1, 'acc1', 'pwd1', '2023-01-01', 10000, 'active', 1, 's1'),
(2, 'acc2', 'pwd2', '2023-01-02', 20000, 'active', 2, 's2'),
(3, 'acc3', 'pwd3', '2023-01-03', 30000, 'active', 3, 's3'),
(4, 'acc4', 'pwd4', '2023-01-04', 40000, 'active', 4, 's4'),
(5, 'acc5', 'pwd5', '2023-01-05', 50000, 'active', 5, 's5'),
(6, 'acc6', 'pwd6', '2023-01-06', 60000, 'active', 6, 's6'),
(7, 'acc7', 'pwd7', '2023-01-07', 70000, 'active', 7, 's7'),
(8, 'acc8', 'pwd8', '2023-01-08', 80000, 'active', 8, 's8'),
(9, 'acc9', 'pwd9', '2023-01-09', 90000, 'active', 9, 's9'),
(10, 'acc10', 'pwd10', '2023-01-10', 100000, 'active', 10, 's10');

-- stocks 테이블에 더미 데이터 삽입
INSERT INTO stocks (stock_id, stock_name, stock_code, stock_listing, capital, face_value, market_capital, transaction_amount, eps, bps, roe) VALUES
('s1', 'Stock1', 'CODE1', TRUE, 1000, 10, 100000, 50000, 5, 10, 15),
('s2', 'Stock2', 'CODE2', TRUE, 2000, 20, 200000, 100000, 6, 11, 16),
('s3', 'Stock3', 'CODE3', TRUE, 3000, 30, 300000, 150000, 7, 12, 17),
('s4', 'Stock4', 'CODE4', TRUE, 4000, 40, 400000, 200000, 8, 13, 18),
('s5', 'Stock5', 'CODE5', TRUE, 5000, 50, 500000, 250000, 9, 14, 19),
('s6', 'Stock6', 'CODE6', TRUE, 6000, 60, 600000, 300000, 10, 15, 20),
('s7', 'Stock7', 'CODE7', TRUE, 7000, 70, 700000, 350000, 11, 16, 21),
('s8', 'Stock8', 'CODE8', TRUE, 8000, 80, 800000, 400000, 12, 17, 22),
('s9', 'Stock9', 'CODE9', TRUE, 9000, 90, 900000, 450000, 13, 18, 23),
('s10', 'Stock10', 'CODE10', TRUE, 10000, 100, 1000000, 500000, 14, 19, 24);

-- stocks_holding 테이블에 더미 데이터 삽입
INSERT INTO stocks_holding (stock_holding_id, stock_id, current_price) VALUES
(1, 's1', 100.00),
(2, 's2', 200.00),
(3, 's3', 300.00),
(4, 's4', 400.00),
(5, 's5', 500.00),
(6, 's6', 600.00),
(7, 's7', 700.00),
(8, 's8', 800.00),
(9, 's9', 900.00),
(10, 's10', 1000.00);

-- stocks_itrs 테이블에 더미 데이터 삽입
INSERT INTO stocks_itrs (stock_itrs_id, stock_id, cur_price) VALUES
('itrs1', 's1', 110.00),
('itrs2', 's2', 210.00),
('itrs3', 's3', 310.00),
('itrs4', 's4', 410.00),
('itrs5', 's5', 510.00),
('itrs6', 's6', 610.00),
('itrs7', 's7', 710.00),
('itrs8', 's8', 810.00),
('itrs9', 's9', 910.00),
('itrs10', 's10', 1010.00);

-- users 테이블에 더미 데이터 삽입
INSERT INTO users (user_id, user_name, gender, email, pwd, birth_day, phone, stock_holding, account_no, stock_id, stock_itrs_id) VALUES
(1, 'User1', 1, 'user1@example.com', 'pwd1', '1990-01-01', '010-1111-1111', 1, 1, 's1', 'itrs1'),
(2, 'User2', 0, 'user2@example.com', 'pwd2', '1990-02-02', '010-2222-2222', 2, 2, 's2', 'itrs2'),
(3, 'User3', 1, 'user3@example.com', 'pwd3', '1990-03-03', '010-3333-3333', 3, 3, 's3', 'itrs3'),
(4, 'User4', 0, 'user4@example.com', 'pwd4', '1990-04-04', '010-4444-4444', 4, 4, 's4', 'itrs4'),
(5, 'User5', 1, 'user5@example.com', 'pwd5', '1990-05-05', '010-5555-5555', 5, 5, 's5', 'itrs5'),
(6, 'User6', 0, 'user6@example.com', 'pwd6', '1990-06-06', '010-6666-6666', 6, 6, 's6', 'itrs6'),
(7, 'User7', 1, 'user7@example.com', 'pwd7', '1990-07-07', '010-7777-7777', 7, 7, 's7', 'itrs7'),
(8, 'User8', 0, 'user8@example.com', 'pwd8', '1990-08-08', '010-8888-8888', 8, 8, 's8', 'itrs8'),
(9, 'User9', 1, 'user9@example.com', 'pwd9', '1990-09-09', '010-9999-9999', 9, 9, 's9', 'itrs9'),
(10, 'User10', 0, 'user10@example.com', 'pwd10', '1990-10-10', '010-1010-1010', 10, 10, 's10', 'itrs10');

-- orders 테이블에 더미 데이터 삽입
INSERT INTO orders (order_id, customer_id, account_id, stock_id, orders_quantity, orders_price, orders_ordertype, orders_dt) VALUES
(1, 1, 1, 's1', 10, 100.00, 'buy', '2023-01-01 10:00:00'),
(2, 2, 2, 's2', 20, 200.00, 'buy', '2023-01-02 11:00:00'),
(3, 3, 3, 's3', 30, 300.00, 'buy', '2023-01-03 12:00:00'),
(4, 4, 4, 's4', 40, 400.00, 'buy', '2023-01-04 13:00:00'),
(5, 5, 5, 's5', 50, 500.00, 'buy', '2023-01-05 14:00:00'),
(6, 6, 6, 's6', 60, 600.00, 'buy', '2023-01-06 15:00:00'),
(7, 7, 7, 's7', 70, 700.00, 'buy', '2023-01-07 16:00:00'),
(8, 8, 8, 's8', 80, 800.00, 'buy', '2023-01-08 17:00:00'),
(9, 9, 9, 's9', 90, 900.00, 'buy', '2023-01-09 18:00:00'),
(10, 10, 10, 's10', 100, 1000.00, 'buy', '2023-01-10 19:00:00');

-- trade_histories 테이블에 더미 데이터 삽입
INSERT INTO trade_histories (trade_id, histories_quantity, histories_price, trade_type, trade_datetime, account_no, customer_id, stock_id) VALUES
(1, 10, 110.00, 'buy', '2023-01-01 10:00:00', 1, 1, 's1'),
(2, 20, 210.00, 'buy', '2023-01-02 11:00:00', 2, 2, 's2'),
(3, 30, 310.00, 'buy', '2023-01-03 12:00:00', 3, 3, 's3'),
(4, 40, 410.00, 'buy', '2023-01-04 13:00:00', 4, 4, 's4'),
(5, 50, 510.00, 'buy', '2023-01-05 14:00:00', 5, 5, 's5'),
(6, 60, 610.00, 'buy', '2023-01-06 15:00:00', 6, 6, 's6'),
(7, 70, 710.00, 'buy', '2023-01-07 16:00:00', 7, 7, 's7'),
(8, 80, 810.00, 'buy', '2023-01-08 17:00:00', 8, 8, 's8'),
(9, 90, 910.00, 'buy', '2023-01-09 18:00:00', 9, 9, 's9'),
(10, 100, 1010.00, 'buy', '2023-01-10 19:00:00', 10, 10, 's10');

-- news 테이블에 더미 데이터 삽입
INSERT INTO news (news_id, news_title, news_content, written_at, news_source, news_url, news_created_at, news_updated_at, stock_holding_id, stock_itrs_id, stock_id) VALUES
(1, 'Title1', 'Content1', '2023-01-01 10:00:00', 'Source1', 'http://example.com/1', '2023-01-01 10:00:00', '2023-01-01 11:00:00', 1, 'itrs1', 's1'),
(2, 'Title2', 'Content2', '2023-01-02 11:00:00', 'Source2', 'http://example.com/2', '2023-01-02 11:00:00', '2023-01-02 12:00:00', 2, 'itrs2', 's2'),
(3, 'Title3', 'Content3', '2023-01-03 12:00:00', 'Source3', 'http://example.com/3', '2023-01-03 12:00:00', '2023-01-03 13:00:00', 3, 'itrs3', 's3'),
(4, 'Title4', 'Content4', '2023-01-04 13:00:00', 'Source4', 'http://example.com/4', '2023-01-04 13:00:00', '2023-01-04 14:00:00', 4, 'itrs4', 's4'),
(5, 'Title5', 'Content5', '2023-01-05 14:00:00', 'Source5', 'http://example.com/5', '2023-01-05 14:00:00', '2023-01-05 15:00:00', 5, 'itrs5', 's5'),
(6, 'Title6', 'Content6', '2023-01-06 15:00:00', 'Source6', 'http://example.com/6', '2023-01-06 15:00:00', '2023-01-06 16:00:00', 6, 'itrs6', 's6'),
(7, 'Title7', 'Content7', '2023-01-07 16:00:00', 'Source7', 'http://example.com/7', '2023-01-07 16:00:00', '2023-01-07 17:00:00', 7, 'itrs7', 's7'),
(8, 'Title8', 'Content8', '2023-01-08 17:00:00', 'Source8', 'http://example.com/8', '2023-01-08 17:00:00', '2023-01-08 18:00:00', 8, 'itrs8', 's8'),
(9, 'Title9', 'Content9', '2023-01-09 18:00:00', 'Source9', 'http://example.com/9', '2023-01-09 18:00:00', '2023-01-09 19:00:00', 9, 'itrs9', 's9'),
(10, 'Title10', 'Content10', '2023-01-10 19:00:00', 'Source10', 'http://example.com/10', '2023-01-10 19:00:00', '2023-01-10 20:00:00', 10, 'itrs10', 's10');

-- news_comment 테이블에 더미 데이터 삽입
INSERT INTO news_comment (comment_id, comment_written_at, comment_content, news_id, stock_id) VALUES
(1, '2023-01-01 10:00:00', 'Comment1', 1, 's1'),
(2, '2023-01-02 11:00:00', 'Comment2', 2, 's2'),
(3, '2023-01-03 12:00:00', 'Comment3', 3, 's3'),
(4, '2023-01-04 13:00:00', 'Comment4', 4, 's4'),
(5, '2023-01-05 14:00:00', 'Comment5', 5, 's5'),
(6, '2023-01-06 15:00:00', 'Comment6', 6, 's6'),
(7, '2023-01-07 16:00:00', 'Comment7', 7, 's7'),
(8, '2023-01-08 17:00:00', 'Comment8', 8, 's8'),
(9, '2023-01-09 18:00:00', 'Comment9', 9, 's9'),
(10, '2023-01-10 19:00:00', 'Comment10', 10, 's10');

