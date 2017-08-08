import os
import pandas
import synapseclient
from nose.tools import assert_equals
from pandas.util.testing import assert_frame_equal

syn = synapseclient.login()

standard_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/common/minimal_Sage_standard.json'
analysis_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/common/minimal_Sage_analysis.json'
dhart_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/dhart_annotations.json'
genie_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/genie_annotations.json'
neuro_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/neuro_annotations.json'
nf_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/nf_annotations.json'
ngs_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/ngs_annotations.json'
onc_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/onc_annotations.json'
tool_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/tool_annotations.json'
toolExtended_path = 'https://raw.githubusercontent.com/Sage-Bionetworks/synapseAnnotations/master/synapseAnnotations/data/toolExtended_annotations.json'

paths = [standard_path, analysis_path, dhart_path, genie_path, neuro_path, nf_path, ngs_path, onc_path, tool_path,
         toolExtended_path]
names = ['standard', 'analysis', 'dhart', 'genie', 'neuro', 'nf', 'ngs', 'onc', 'tool', 'toolExtended']

# test table synID
tableSynId = "syn10265158"

all_projects = []

currentTable = syn.tableQuery("SELECT * FROM %s" % tableSynId)
currentTable = currentTable.asDataFrame()

def json2flatten(path, project):
    # fetch and read raw json objects from its' github url and decode the json object to its raw format
    json_record = pandas.read_json(path)

    # grab annotations with empty enumValue lists i.e. don't require normalization and structure their schema
    empty_vals = json_record.loc[json_record.enumValues.str.len() == 0]
    empty_vals = empty_vals.drop('enumValues', axis=1)

    empty_vals['enumValues_description'] = ""
    empty_vals['enumValues_source'] = ""
    empty_vals['enumValues_value'] = ""
    empty_vals['project'] = project

    empty_vals.set_index(empty_vals['name'], inplace=True)

    # for each value list object
    flatten_vals = []
    json_record = json_record.loc[json_record.enumValues.str.len() > 0]
    json_record.reset_index(inplace=True)

    for i, jsn in enumerate(json_record['enumValues']):
        df = pandas.io.json.json_normalize(json_record['enumValues'][i])
        # re-name columns to match table on synapse schema
        df = df.rename(columns={'value': 'enumValues_value', 'description': 'enumValues_description',
                                'source': 'enumValues_source'})

        # grab key information in its row, expand it by values dimention and append its key-columns to flattened values
        rows = json_record.loc[i:i, json_record.columns != 'enumValues']
        repeats = pandas.concat([rows] * len(df.index))
        repeats.set_index(df.index, inplace=True)
        flatten_df = pandas.concat([repeats, df], axis=1)
        # append project category / annotating the annotations for project filtering
        flatten_df['project'] = project
        flatten_df.set_index(flatten_df['name'], inplace=True)

        flatten_vals.append(flatten_df)

    flatten_vals.append(empty_vals)

    return flatten_vals

for i, p in enumerate(paths):
    data = json2flatten(p, names[i])
    project_df = pandas.concat(data)
    all_projects.append(project_df)

# append/concat/collapse all normalized dataframe annotations into one dataframe
all_projects_df = pandas.concat(all_projects)

# re-arrange columns/fields
all_projects_df = all_projects_df[
    ["name", "description", "columnType", "maximumSize", "enumValues_value", "enumValues_description",
     "enumValues_source", "project"]]

all_projects_df.columns = ["key", "description", "columnType", "maximumSize", "value", "valuesDescription",
                           "source", "project"]

# save the table as a csv file
all_projects_df.to_csv("annot.csv", sep=',', index=False, encoding="utf-8")
all_projects_df = pandas.read_csv('annot.csv', delimiter=',', encoding="utf-8")
os.remove("annot.csv")


def check_keys():
    """
    Example: nosetests -vs tests/unit/test_json2synapse.py:check_keys
    :return: None or assert_equals Error message
    """
    for i, p in enumerate(paths):
        table_key_set = set(currentTable[currentTable['project'] == names[i]].key.unique())
        json_record = pandas.read_json(p)
        json_key_set = set(json_record['name'])
        # print("json_key_set", len(json_key_set), json_key_set)
        # print("table_key_set", len(table_key_set), table_key_set)
        assert_equals(len(json_key_set), len(table_key_set), ' '.join(["module name:", names[i], "synapseAnnotations "
                                                                                                 "github repo keys "
                                                                                                 "length",
                                                                       str(len(json_key_set)), "don't match synapse "
                                                                                               "table "
                                                                                               "length",
                                                                       str(len(table_key_set))]))


def compare_key_values():
    """
    Example: nosetests -vs tests/unit/test_json2synapse.py:compare_key_values

    :return: If the synapse table key-value columns data frame matches exactly with the normalized
    json key-value columns data frame it returns None otherwise it generates an error with the % mismatch.

    It is required for both data frames to be sorted exactly the same, otherwise a small % mismatch is reported.
    """
    # subset dataframe to only compare the unique keys (key-value)

    synapse_df = currentTable.loc[:, ('key', 'value')]
    github_df = all_projects_df.loc[:, ('key', 'value')]

    # sort by key (key-value pair)
    synapse_df.sort_values(['key', 'value'], ascending=[True, True], inplace=True)
    github_df.sort_values(['key', 'value'], ascending=[True, True], inplace=True)

    # set the columns as index (may not be needed)
    synapse_df.set_index(['key', 'value'], inplace=True, drop=False)
    github_df.set_index(['key', 'value'], inplace=True, drop=False)

    # reset the index (pandas assigns unique labels per each multi-key value)
    synapse_df.reset_index(inplace=True, level=None, drop=True)
    github_df.reset_index(inplace=True, level=None, drop=True)

    #synapse_df.to_csv("df1.csv")
    #github_df.to_csv("df2.csv")

    # compare the dataframes
    assert_frame_equal(github_df, synapse_df, check_names=False)

