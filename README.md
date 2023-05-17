DISCLAIMER: This project was not originally intended for a public repo, and as a result, the documentation could be much better.  I do not recommend the use of these scripts to anyone without a thorough understanding of the program.  If anything, this script should provide ideas or inspiration for your own creations.  Use at your own risk.

I started working on this personal day trading bot back in September 2022 and this has turned into my biggest personal project since (it is currently May 2023).
This repository should probably be private but I've removed the file that holds the trading strategy/alpha so what's left is a TD Ameritrade "API wrapper" that
was created specifically for my personal trading strategy using options derivatives.  

Shout out to https://github.com/areed1192 for his amazing youtube channel.  I had already created most of my program before discovering his videos/github but if you want a more cleaner and user friendly TD Ameritrade API wrapper with video tutorials, please check out his version and youtube channel.  I found his channel when I was trying to add streaming data API functionality to my program, and I basically adopted one of his older implementations of the streaming data API into my program.

How it works:
Livetrade: When the program is fed a signal like "SPX 4000c 1.25", it will send an OCO(Order Cancels Order) Limit Buy order with a Limit sell and Stop sell that you can set by adjusting the trade parameters.  Depending on the SIZE (number of contracts), each order sent out will have a different Limit Sell target (scaling out strategy).  If the first Limit Sell is filled, all the Stop Sell orders will be moved to break-even level to ensure that the trade can only profit or break-even.

Papertrade:
Used for testing the performance of a strategy by using options quotes and buying and selling when given "entry" and "exit" signals.  Trades are recorded in a paperdata.csv file.

Plot:
Given a transactions.csv in the same directory, running this script will plot out a net profit waterfall chart that can be used to visualize trading performance.

Scankey:
Currently in progress - Using the camera on your computer, you can scan a QR code of your keys before starting the trading bot.
