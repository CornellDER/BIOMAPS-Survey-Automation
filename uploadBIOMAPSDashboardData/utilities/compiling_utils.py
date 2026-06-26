import pandas as pd
from utilities.qualtrics_utils import get_cis_response_data, download_responses_as_df
from utilities.scoring_utils import validate_responses, score_biomaps
from utilities.processing_utils import simplify_columns, label_demographics

def compile_course_data(instructor_id):
    """
    Create a dataframe with all the formatted data for a course.
    This function returns a dataframe that is formatted to be easily appended to the dashboard data file
    and a string that specifies which assessment corresponds to this instructor_id. 

    Keyword arguments:
    instructor_id -- string specifying the instructor's response ID in the course information survey
    """
    # Obtain survey data from instructor ID
    result = get_cis_response_data(instructor_id)
    survey_type = result["survey_type"]
    
    # Download the survey results
    df = download_responses_as_df(result["survey_id"])
    
    # Validate the survey results
    df = validate_responses(df, survey_type)
    
    # Score the survey results
    df = score_biomaps(df, survey_type)

    # Label demographics for easier reading
    df = label_demographics(df, survey_type)

    # Load headers file for simplify_columns
    headers = pd.read_csv(f'utilities/ColumnOrdering/{survey_type}_Headers.csv')

    # Simplify columns
    df = simplify_columns(df = df, 
                        column_ordering = headers, 
                        instructor_id = instructor_id, 
                        course_type = result["course_type"], 
                        class_size = result["class_size"])
    
    # Return the data and course type
    return df, survey_type