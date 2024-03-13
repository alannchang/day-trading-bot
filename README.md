# Day Trading Bot

## Demo

![](https://github.com/alannchang/day-trading-bot/blob/main/live-trade-demo-1.gif)

## What is this?

*UPDATE: Because my day trading thesis was unsuccessful, consider this repo to be an archive, not an actively managed project.
While my strategy/bot has not been consistently profitable, I have learned a lot during the process.
I personally do not recommend trading based off alerts exclusively. Trade at your own risk.*

I started working on this experimental day trading bot in September 2022 as a way to test an idea I had; I wanted to know if it was possible to profit off
discord server alerts, specifically for options plays (https://www.investopedia.com/terms/o/option.asp).  The problem with trying to follow these alerts is
that after an alert is announced on a discord server, execution time by manual, human input is simply too slow.  So I sought out to automate and decrease the latency of 
this execution using my novice Python skills.

DISCLAIMER: This project was not originally intended for a public repo, and as a result, the documentation could be much better.  I do not recommend the use of these scripts to anyone without a thorough understanding of its contents.  If anything, this script should provide ideas or inspiration for your own creations.  Use at your own risk.

Shout out to https://github.com/areed1192 for his amazing youtube channel.  I had already created most of this script before discovering his videos/github but if you want a more cleaner and user friendly TD Ameritrade API wrapper with video tutorials, please check out his version and youtube channel.  I found his channel when I was trying to add streaming data API functionality to my program, and I've adopted one of his older implementations of the streaming data API into my script.

## How it works:
Livetrade: When the script is fed a signal like "SPX 4000c 1.25", it will send an OCO(Order Cancels Order) Limit Buy order with a Limit sell and Stop sell that you can set by adjusting the trade parameters.  Depending on the SIZE (number of contracts), each order sent out will have a different Limit Sell target (scaling out strategy).  If the first Limit Sell is filled, all the Stop Sell orders will be moved to break-even level to ensure that the trade can only profit or break-even.

#### Papertrade:
Used for testing the theoretical performance of a strategy by using options quotes and buying and selling when given "entry" and "exit" signals.  Trades are recorded in a dataframe inside paperdata.csv file.

#### Plot:
Given a transactions.csv in the same directory, running this script will plot out a net profit/loss waterfall chart that can be used to visualize trading performance.
![](https://github.com/alannchang/day-trading-bot/blob/main/sample-plot.png)
