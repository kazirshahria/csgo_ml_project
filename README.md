# CS:GO ML Project 🕹️

**Goal**: Predict a player's headshot and kill count in the game CS:GO with machine learning, specifally with regression models.

The dataset that was used to train the models cannot be disclosed. However, it involves historical data for **ALL** players who are involved in competitve gaming. The data is also stored in a MySQL database that is operated on AWS.

# Model Summary 👨‍💻

The model that was trained and exported for making future predictions was an XGBoost Regressor.

**R2 Score**
- Kills: 0.7199
- Headshots: 0.645

**Mean Absolute Error**
- Kills: 5.658
- Headshots: 3.483

**Root Mean Square Error**
- Kills: 7.3899
- Headshots: 4.552

The R2 scores are moderate indicating a decent fit. When backtracking the results, on average, the unders have a higher hit rate. The overall performance fluctuates and hovers around 52% hit rate.

# Contact me 🙂

I cannot disclose anymore on this project, but the code and modeling can be found in this repository. Feel free to also contact me using the link below.

[Linkedin](https://www.linkedin.com/in/kazishahria/)