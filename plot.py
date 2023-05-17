import pandas as pd
import numpy as np
import plotly.graph_objects as go

# read in the CSV file as a pandas DataFrame
df = pd.read_csv('transactions.csv', skipfooter=1, engine='python')

# initialize net amounts to NaN for each row
df['Net'] = np.nan

# calculate the net amount for each security
net_amounts = {'Bought': [], 'Sold': []}
counter = 0
for index, row in df.iterrows():
    symbol = row['SYMBOL']
    amount = row['AMOUNT']
    if row['DESCRIPTION'].startswith('Bought'):
        if row['DESCRIPTION'].split()[1] == "to":
            counter += int(row['DESCRIPTION'].split()[3])
        else:
            counter += int(row['DESCRIPTION'].split()[1])
        net_amounts['Bought'].append(amount)
    elif row['DESCRIPTION'].startswith('Sold'):
        if row['DESCRIPTION'].split()[1] == "to":
            counter -= int(row['DESCRIPTION'].split()[3])
        else:
            counter -= int(row['DESCRIPTION'].split()[1])
        net_amounts['Sold'].append(amount)

        if counter == 0:
            dict_values = sum(net_amounts['Bought']) + sum(net_amounts['Sold'])
            net = dict_values
            df.at[index, 'Net'] = net
            net_amounts['Bought'].clear()
            net_amounts['Sold'].clear()

# drop empty columns
df.dropna(axis='columns', how='all', inplace=True)

# filter out rows with NaN in the Net column
df = df[df['Net'].notna()]

# create a new index for the rows where 'Net' has values
index = pd.RangeIndex(len(df.index))

# create a new column for the text to display on the bars, including the date
df['text'] = df['Net'].apply(lambda x: f'{x:.2f}') + '<br>' + df['DATE'].apply(str)

# set the color of the bars based on net amount
df['color'] = 'red'
df.loc[df['Net'] > 0, 'color'] = 'green'

# create waterfall chart
fig = go.Figure(go.Waterfall(
    x=index,
    y=df['Net'],
    textposition='outside',
    orientation='v',
    decreasing={'marker': {'color': '#FF0018'}},
    increasing={'marker': {'color': '#00C805'}},
    totals={'marker': {'color': 'blue'}},
    connector={'line': {'color': 'gray', 'dash': 'dot'}},
    name=''
))

# set the text for the bars to display only the net amount (without the date)
fig.data[0].text = df['Net'].apply(lambda x: f'{x:.2f}')

# set the text template to display only the net amount (without the date)
fig.update_traces(texttemplate='%{y:.2f}', textposition='inside')

# set layout options to remove legend and set bar and group spacing
fig.update_layout(showlegend=False, waterfallgap=0, plot_bgcolor='grey', title='Performance', xaxis_title='Trades', yaxis_title='Total PnL')

# set the hover template to show the date when hovering over a bar
fig.update_traces(hovertemplate='%{text}<extra></extra>')

fig.show()
