import pandas as pd
import numpy as np
from utilities.processing_utils import process_names

def validate_responses(df, survey_type):
    """
    Validate survey responses to BIOMAPS assessments

    Keyword arguments:
    df -- pandas dataframe of student responses to an assessment
    survey_type -- string of the assessment being queried. It can be one of these: "EcoEvo-MAPS", "Capstone", "Phys-MAPS", or "GenBio-MAPS".
    """

    # Check consent and age
    if survey_type == "EcoEvo-MAPS":
        consent_question = "Q55_5" 
        consent_valid_answer = 5
        age_question = "D.1" 
        consent_valid_age = 1
    elif survey_type == "Capstone":
        consent_question = "Q68_5"
        consent_valid_answer = 5
        age_question = "Q69"
        consent_valid_age = 5
    elif survey_type == "Phys-MAPS":
        consent_question = "Q46_5"
        consent_valid_answer = 5
        age_question = "Q18"
        consent_valid_age = 1
    elif survey_type == "GenBio-MAPS":
        consent_question = "Q298_5"
        consent_valid_answer = 5
        age_question = "Age"
        consent_valid_age = 1

    #df['Valid'] = np.nan # start with empty column
    #df.loc[(df[consent_question] == consent_valid_answer) & (df[age_question] == consent_valid_age), 'Valid'] = 1 # if they consent and are 18 or older, it's valid 
    #df.loc[(df[consent_question] != consent_valid_answer) | (df[age_question] != consent_valid_age), 'Valid'] = 0 # if they do not consent or are not 18, it's not valid
    df["Valid"] = (
        (df[consent_question] == consent_valid_answer)
        & (df[age_question] == consent_valid_age)
    ).astype(int) # if they consent and are 18 or older, it's valid; otherwise, it's not valid

    # Check survey finished
    df = df[df['Finished'] == 1]

    # Drop duplicate names and IDs
    df = process_names(df, survey_type)
    # Could change the following, but will keep it as it is
    df = df.drop_duplicates(subset = ['FullName']).drop_duplicates(subset = ['ID']) # Drop second entry if there are duplicate full names
    #df = df.drop_duplicates(subset = ['FullName', 'ID']) # Drop second entry if there are duplicate full names; treat only combo as unique

    # Check name and ID given
    df = df.dropna(how = 'all', subset = ['ID', 'Last_Name', 'First_Name']) # drops responses with no identifying information, just in case

    # Reset index for cleanliness
    df = df.reset_index(drop=True)

    return df

def score_biomaps(df, survey_type):
    """
    Calculate total score, scores for individual questions, and construct scores

    Keyword arguments:
    df -- pandas dataframe of student responses to BIOMAPS
    survey_type -- string of the assessment being queried. It can be one of these: "EcoEvo-MAPS", "Capstone", "Phys-MAPS", or "GenBio-MAPS".
    """
    # Load the relevant keys for scoring
    solutions_df = pd.read_csv(f'utilities/AssessmentSolutions/{survey_type}_Solutions.csv')
    constructs_df = pd.read_csv(f'utilities/AssessmentSolutions/{survey_type}_Constructs.csv')

    # Create an empty DataFrame with the same index as df
    scored_df = pd.DataFrame(index=df.index)
    
    # Score individual items
    # Dict to hold all scored series
    scored_columns = {}
    
    # Loop over each row in solutions_df to compute scores
    for _, row in solutions_df.iterrows():
        scored_column = row['ScoredQuestion']
        raw_column = row['UnscoredQuestion']
        correct_answer = row['CorrectAnswer']
        
        if survey_type == 'GenBio-MAPS':
            # GenBio gives each student a random assortment of questions
            # We score differently because students only get scored on questions they've shown
            # We can tell if a student was shown a question by looking at the time spent on each page
    
            timing_column = row['TimingQuestion']
            # Initialize all as NaN (not shown)
            scored_series = pd.Series(np.nan, index=df.index)
            
            # For rows where timing_column is not null (question was shown)
            was_shown = pd.notnull(df[timing_column])
            
            # Fill in 1/0 only for students who were shown the question
            scored_series[was_shown] = (df.loc[was_shown, raw_column] == correct_answer).astype(int)        
        else:
            # For the other assessments, students are shown every question
            # Compare df[raw_column] to correct_answer and cast as integer to get 1/0
            scored_series = (df[raw_column] == correct_answer).astype(int)
    
        scored_columns[scored_column] = scored_series
    
    # Combine all scored columns into final DataFrame
    scored_df = pd.concat(scored_columns, axis=1)

    # Calculate total score
    if survey_type == 'GenBio-MAPS':
        # If GenBio, have to account for students not seeing some questions
        scored_df['SC_Total_Score'] = scored_df.sum(axis=1) / scored_df.count(axis=1)
    else:
        # Otherwise, can just use number of questions for score
        scored_df['SC_Total_Score'] = scored_df.sum(axis=1) / len(scored_df.columns)

    # Score constructs
    for construct in constructs_df.columns:
        # get list of question columns for this construct, drop NaNs
        construct_questions = constructs_df[construct].dropna().tolist()
        
        # compute average score per student on those questions
        if survey_type == 'GenBio-MAPS':
            # If GenBio, have to account for students not seeing some questions
            scored_df[construct] = scored_df[construct_questions].sum(axis=1) / scored_df[construct_questions].count(axis=1)
        else:
            # Otherwise, can just use number of questions for score
            scored_df[construct] = scored_df[construct_questions].sum(axis=1) / len(construct_questions)

    # Concatenate onto original dataframe
    df = pd.concat([df, scored_df], axis = 1)
    
    return df