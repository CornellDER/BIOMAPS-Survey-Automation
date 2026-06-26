import pandas as pd
import numpy as np

def process_names(df, survey_type):
    """
    Process students' names and IDs for processing

    Keyword arguments:
    df -- pandas dataframe of student responses to BIOMAPS
    survey_type -- string of the assessment being queried. It can be one of these: "EcoEvo-MAPS", "Capstone", "Phys-MAPS", or "GenBio-MAPS".
    """
    ## First, rename the columns for consistency
    if survey_type == "EcoEvo-MAPS":
        df = df.rename(columns = {'PartInfo_3_TEXT':'ID', 
                                  'PartInfo_2_TEXT':'Last_Name', 
                                  'PartInfo_1_TEXT':'First_Name'})
    elif survey_type == "Capstone":
        df = df.rename(columns = {'ID_3_TEXT':'ID', 
                                  'ID_2_TEXT':'Last_Name', 
                                  'ID_1_TEXT':'First_Name'})
    elif survey_type == "Phys-MAPS":
        df = df.rename(columns = {'Q11_2_TEXT':'Last_Name', 
                                  'Q11_1_TEXT':'First_Name'})
    elif survey_type == "GenBio-MAPS":
        df = df.rename(columns = {'ID2_1_TEXT':'ID', 
                                  'ID1_2_TEXT':'Last_Name', 
                                  'ID1_1_TEXT':'First_Name'})

    ## Combine names into FullName and make an ID column
    df['FullName'] = (df['First_Name'].astype(str).str.lower() + df['Last_Name'].astype(str).str.lower()).str.replace(r'\W', '', regex=True) # Get full name in lower case with no white space
    df = df[df['FullName'].map(len) > 2] # Keep only full names with more than 2 characters
    if survey_type == 'Phys-MAPS':
        # Phys has no ID question
        df['ID'] = df['FullName']
    else:
        # The other assessments have an ID question
        df['ID'] = df['ID'].astype(str).str.split('@').str.get(0).str.lower() # Keep only first part of email addresses and take the lower case of all ids
    
    return df

def label_gender(row, survey_type):
    """
    Convert a row's gender demographics to a single output.
    Note: this code is nearly unmodified from Cole's version.

    Keyword arguments:
    row -- a single row from a pandas dataframe of student responses to an assessment
    survey_type -- string of the assessment being queried. It can be one of these: "EcoEvo-MAPS", "Capstone", "Phys-MAPS", or "GenBio-MAPS".
    """

    if (survey_type == 'Capstone'):
        if (row['Gender'] == 1):
            return 'Male'
        elif (row['Gender'] == 2):
            return 'Female'
        else:
            return ''
    elif (survey_type == 'EcoEvo-MAPS'):
        if (row['D.12'] == 1):
            return 'Female'
        elif (row['D.12'] == 2):
            return 'Male'
        else:
            return ''
    elif (survey_type == 'GenBio-MAPS'):
        if (row['Gen'] == 1):
            return 'Female'
        elif (row['Gen'] == 2):
            return 'Male'
        else:
            return ''
    elif (survey_type == 'Phys-MAPS'):
        if (row['Q30'] == 1):
            return 'Female'
        elif (row['Q30'] == 2):
            return 'Male'
        else:
            return ''

def label_URM_status(df, survey_type):
    """
    Convert a dataframe's race/ethnicity data into simplified URM status.
    Note: this code is nearly unmodified from Cole's version.

    Keyword arguments:
    df -- pandas dataframe of student responses to an assessment
    survey_type -- string of the assessment being queried. It can be one of these: "EcoEvo-MAPS", "Capstone", "Phys-MAPS", or "GenBio-MAPS".
    """
    # white and asian/asian american students are coded as 'Majority', all others are coded as 'URM'
    if (survey_type == 'Capstone'):
        conditions = [
            df['Race_1'] == 1,
            df['Race_2'] == 1,
            df['Race_3'] == 1,
            df['Race_4'] == 1,
            df['Race_5'] == 1,
            df['Race_6'] == 1,
            df['Race_7'] == 1
        ]

        output = ['URM', 'Majority', 'URM', 'URM', 'URM', 'Majority', 'URM']
    elif (survey_type == 'EcoEvo-MAPS'):
        conditions = [
            df['D.13_4'] == 1,
            df['D.13_5'] == 1,
            df['D.13_6'] == 1,
            df['D.13_7'] == 1,
            df['D.13_9'] == 1,
            df['D.13_1'] == 1,
            df['D.13_2'] == 1
        ]

        output = ['URM'] * 5 + ['Majority'] * 2
    elif (survey_type == 'GenBio-MAPS'):
        conditions = [
            df['Ethn_1'] == 1,
            df['Ethn_2'] == 1,
            df['Ethn_3'] == 1,
            df['Ethn_5'] == 1,
            df['Ethn_6'] == 1,
            df['Ethn_7'] == 1,
            df['Ethn_9'] == 1
        ]

        output = ['URM', 'Majority', 'Majority', 'URM', 'URM', 'URM', 'URM']
    elif (survey_type == 'Phys-MAPS'):
        conditions = [
            df['Q16_1'] == 1,
            df['Q16_5'] == 1,
            df['Q16_6'] == 1,
            df['Q16_7'] == 1,
            df['Q16_9'] == 1,
            df['Q16_2'] == 1,
            df['Q16_3'] == 1
        ]

        output = ['URM'] * 5 + ['Majority'] * 2

    df['URMStatus'] = np.select(conditions, output, None)
    return df

def label_demographics(df, survey_type):
    """
    Convert demographic columns to readable labels.

    Keyword arguments:
    df -- pandas dataframe of student responses to an assessment
    survey_type -- string of the assessment being queried. It can be one of these: "EcoEvo-MAPS", "Capstone", "Phys-MAPS", or "GenBio-MAPS".
    """

    df['SexGender'] = df.apply(lambda x: label_gender(x, survey_type = survey_type), axis = 1)
    df = label_URM_status(df, survey_type)

    if(survey_type == 'Capstone'):
        df['ClassStanding'] = df['CY'].map({1:'Freshman', 
                                            2:'Sophomore/Junior', 
                                            3:'Sophomore/Junior', 
                                            4:'Senior', 
                                            5:'Grad'})
    elif(survey_type == 'EcoEvo-MAPS'):
        df['ClassStanding'] = df['D.2'].map({1:'Freshman', 
                                             2:'Sophomore/Junior', 
                                             3:'Sophomore/Junior', 
                                             4:'Senior', 
                                             6:'Grad'})
        df['Major'] = df['D.9'].map({1:'Biology', 
                                     2:'Other'})
        df['TransferStatus'] = df['D.3'].map({1:'Transfer student', 
                                              2:'Not a transfer student'})
        df['ELL'] = df['D.14'].map({1:'English', 
                                    2:'Other'})
        df['ParentEducation'] = df['D.17'].map({1:'First Gen', 
                                                2:'First Gen', 
                                                3:'First Gen', 
                                                4:'Continuing Gen', 
                                                5:'Continuing Gen',
                                                6:'Continuing Gen', 
                                                7:'Continuing Gen'})
    elif(survey_type == 'GenBio-MAPS'):
        df['ClassStanding'] = df['Class'].map({1:'Freshman', 
                                               2:'Sophomore/Junior', 
                                               3:'Sophomore/Junior', 
                                               4:'Senior', 
                                               6:'Grad'})
        df['TransferStatus'] = df['Trans'].map({1:'Transfer student', 
                                                2:'Not a transfer student'})
        df['Major'] = df['Maj'].map({1:'Life Sciences', 
                                     2:'Other'})
        df['ELL'] = df['Eng'].map({1:'English', 
                                   2:'Other Language'})
        df['ParentEducation'] = df['Educ'].map({1:'First Gen', 
                                                2:'First Gen', 
                                                3:'First Gen', 
                                                4:'Continuing Gen', 
                                                5:'Continuing Gen',
                                                6:'Continuing Gen', 
                                                7:'Continuing Gen'})
    elif(survey_type == 'Phys-MAPS'):
        df['ClassStanding'] = df['Q19'].map({1:'Freshman', 
                                             2:'Sophomore/Junior', 
                                             3:'Sophomore/Junior', 
                                             4:'Senior', 
                                             6:'Grad'})
        df['Major'] = (1 * ((df['Q27'] == 1) | (df['Q42'] == 1))).map({1:'Biology',
                                                                       0:'Other'})
        df['TransferStatus'] = df['Q21'].map({1:'Transfer student', 
                                              2:'Not a transfer student'})
        df['ELL'] = df['Q31'].map({1:'English', 
                                   2:'Other'})
        df['ParentEducation'] = df['Q33'].map({1:'First Gen', 
                                               2:'First Gen', 
                                               3:'First Gen', 
                                               4:'Continuing Gen', 
                                               5:'Continuing Gen',
                                               6:'Continuing Gen', 
                                               7:'Continuing Gen'})

    return df

def simplify_columns(df, column_ordering, instructor_id, course_type, class_size):
    '''
    This function drops unnecessary columns and rearranges the columns to be in the correct order.
    It also adds in class level data as columns.
    '''
    
    # add columns called "Class_ID" and "Class_Size"
    df["Class_ID"] = instructor_id
    df["Class_Size"] = class_size
    df["Class_Level"] = course_type

    # Make and apply class level map
    class_level_map = {
        1: 'Beginning of an introductory course series',
        2: 'End of an introductory course series',
        3: 'Advanced',
        4: 'Other',
        5: 'Graduate'
    }
    df["Class_Level"] = df["Class_Level"].map(class_level_map)
    
    # Keep  and re-order the needed columns 
    columns_to_keep = list(column_ordering.columns.astype(str))
    df = df[columns_to_keep]

    return df