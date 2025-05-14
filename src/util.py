#!/usr/bin/env python
# coding: utf-8

# To work with dataframes
import pandas as pd
# To work with arrays
import numpy as np
# To work with exel files (if only csv files are going to be used, can be ignored)
import xlrd
# To make plots
import matplotlib.pyplot as plt
# To work with files (check if a file exists on the drive, ...)
import os.path
# To work with time like getting the current year
import datetime

###########
# Set up constants

current_year = datetime.date.today().year
provinces = ['AB', 'BC', 'MB', 'NB', 'NL', 'NT', 'NS', 'NU', 'ON', 'PE', \
             'QC', 'SK', 'YT']
names = ['Federal'] + provinces
tax_years = list(range(2020, 2025))

###########

# Here we define a custom exception class to handle most of possible variable quality errors
class CustomException(Exception):
    def __init__(self, message):
        # Call the base class constructor with the custom message
        super().__init__(message)


def clinic(incs, prov, year):
    '''
    This function checks the quality of arguments received by some of the main
    functions (after_tax, before_tax, make_poly) and others and throws custom errors
    for possible problems.

    Parameters
    ----------
    incs: array_like
        Look at definitions in the before_tax function.
    prov: str
    year: int

    Returns
    -------
    If there is no quality issue, parameters would be returned unaltered.
    '''
    ### Check quality of the data.
    ### If clauses are self-expressive.
    if type(incs) != np.ndarray or len(incs.shape) != 1 or np.isnan(incs).sum() > 0 \
       or len(incs) < 1:
        raise CustomException("The first argument (income) must be a one dimensional \
array of positive numbers with at least one element. NaN is not allowed.")
    elif type(year) != int or year not in tax_years:
        raise CustomException(f"The first argument (income) must be a positive integer \
or float and the 3rd argument (year) must be an integer between {tax_years[0]} and \
{tax_years[-1]}.")
    elif prov.upper() not in provinces:
        raise CustomException("The 2nd passed argument must be a valid abbreviation of \
one of Canada's provinces or territories (like 'AB', 'BC', 'NL', 'ON', ...)")
    else:
        return incs, prov.upper(), year


def guide():
    '''
    This function provides a how-to-use guide about main functions after_tax, before_tax,
    after_tax_combo, before_tax_combo and get_poly.

    ------------------------------------------------------

    after_tax(gross_incs, prov, year): calculates the net income for a given gross income

    Parameters
    ----------
    gross_incs: An array of gross incomes for which the net earnings will be calculated.
    prov: Province
    year: Tax year

    Returns
    -------
    net_incs: The array of after_tax incomes obtained for the given before_tax incomes.
    ----------------------------------------------------------

    before_tax(net_incs, prov, year): Calculates the gross income for a given net income.

    Parameters
    ----------
    net_incs: An array of net incomes for which the gross earnings will be calculated.
    prov: Province
    year: Tax year

    Returns
    -------
    gross_incs: The array of before_tax incomes obtained for the given after_tax incomes.


    after_tax_combo(df): Calculates the net income for combinations of gross incomes,
    provinces and years.

    Parameters
    ----------
    df: a dataframe with 3 columns in this sequence: gross income, province and year.

    Returns
    -------
    df: The same dataframe with an added 4rth column containing net incomes.
    ------------------------------------------------------------------

    before_tax_combo ( df ) : Calculates the gross income for combinations of net incomes ,
    provinces and years .

    Parameters
    ----------
    df : a dataframe with 3 columns in this sequence : net income , province and year ...
    ------------------------------------------------------------------
    Returns
    -------
    df : The same dataframe with an added 4rth column containing gross incomes .
    ------------------------------------------------------------------

    get_poly(year ) : Generates the polynomial equations for all provinces for calculating
    the gross income for a given net income . It is enough to be run once everytime
    we need to update the equations .

    Parameters
    ----------
    year : Tax year

    Returns
    -------
    coeff_dict : Directly saves the obtained polynomials ( their coefficients ).
    ------------------------------------------------------------------
    '''

    print(
    """
    -----------------------------------------------------------------------------------
    Guide to call after_tax, before_tax, after_tax_combo, before_tax_combo and get_poly
    functions.
    -----------------------------------------------------------------------------------

    Import the module as follows.

    import tax_calculator

    Then, after_tax, before_tax, after_tax_combo, before_tax_combo and get_poly
    functions of the module can be called using this syntax:
    tax_calculator.after_tax(gross_incs, prov, year)
    OR
    tax_calculator.after_tax_combo(dataframe of combos)

    Also, you can print this guide like this:

    tax_calculator.guide()

    Alternatively, you can directly import the function:

    from tax_calculator import get_poly

Then, call the function using this syntax:

get_poly(year)

In this case, to see the guide you'll need to import it explicitly:

from tax_calculator import guide

Now you can see the instructions using the guide() command.

Calling after_tax (or after_tax_combo) and before_tax (or before_tax_combo) follows
the same rules with the difference that they will return net and gross income,
respectively.

Mandatory arguments for after_tax and before_tax functions:
income: A none negative number.
province: Abbreviation of a Canadian province or territory.
year: A year between 2020 and 2024.

Mandatory arguments for after_tax_combo and before_tax_combo functions:
df: A dataframe of combos of income, province and year (must be the first 3 columns).

"""
)
    

def tax_data(year=2023):
    '''
    Reads all federal and provincial tax information, exemptions and specific factors for
    a specific year.

    Parameters
    ----------
    year: the target year for tax calculation.

    Returns
    -------
    tables: A dictionary containing all provinces and federal tax information for the
            given year. It will be the source of data for all the other functions.
    names: A list containing the keys for the table dictionary. It consists of 'Federal',
           and abbreviations of Canadian provinces and territories.
    '''

        # Set up the file and provinces (sheet for excel) names to read from
    file = '../data/excel_data/tax_rates_' + str(year) + '.xlsx'
    tables = {}

        # Read federal and provincial tax data for the given year from the source
        # excel file or the tax csv files
    path = "../data/tax_rates_" + str(year) + "/"
    for name in names:
            # To directly read from the source excel files
        globals()[f'{name}_df'] = pd.read_excel(file, sheet_name=name)

            # To read from csv tax files
        globals()[f'{name}_df'] = pd.read_csv(path + name + '.csv')
        tables[name] = globals()[f'{name}_df']

    return tables, names


def tax_data_to_csv(year):
    '''
    Reads all federal and provincial tax information, exemptions and specific factors
    for a specific year from excel source and saves them in separate csv files.
    The purpose of having this function is creating or editing the tax rate tables in
    excel files (that is much easier) and then converting them into csv files for
    operational uses.

    Parameters
    ----------
    year: The target year for tax calculation.
    '''

        # Set up the file and sheet names to read from
    file = '../data/excel_data/tax_rates_' + str(year) + '.xlsx'

        # Read federal and provincial tax data for the given year from the source
        # excel file and save them in csv format
    path = "../data/tax_rates_" + str(year) + "/"
    for name in names:
        tax_rate_df = pd.read_excel(file, sheet_name=name)
        tax_rate_df.to_csv(path + name + '.csv', index=False)

    return


def save_poly_xlsx(poly_df, year):
    '''
    Saves calculated polynomials for all territories in sheets of a single excel file.
    This function is optional because there is a similar function to save polynomials
    in csv format too. Either function is used, the parts that read those data needs to
    be adjusted accordingly in the code (just by commenting out or uncommenting the lines).

    Parameters
    ----------
    poly_df : A dataframe that contains provinces' symbols as columns' names and their
              polynomial coefficients. Note that every province has two sets of coefficients:
              1) for low to ordinary; 2) for ordinary to very high incomes.
    year : The tax year
    '''

        # Give a name to the file of polynomial coefficients
    file = '../data/excel_data/polynomials.xlsx'

        # If the data is already exist (for a year), overwrite it
    if os.path.isfile(file):
        with pd.ExcelWriter(file, mode='a', engine="openpyxl", if_sheet_exists='replace') as writer:
            poly_df.to_excel(writer, sheet_name=str(year), index=False)

        # Otherwise create a new sheet in the excel file for the new data
    else:
        with pd.ExcelWriter(file, mode='w', engine="openpyxl") as writer:
            poly_df.to_excel(writer, sheet_name=str(year), index=False)

    print(f"The tax equations for year {year} are successfully saved in {file}.")


def save_poly_csv(poly_df, year):
    '''
    Saves calculated polynomials for all territories in separate csv files.

    Parameters
    ----------
    See save_poly_xlsx
    '''

    path = '../data/tax_rates_' + str(year) + '/'

        # Give a name to the file of polynomial coefficients
    path = '../../data/tax_rates_' + str(year) + "/"
    file = "polynomials-" + str(year) + ".csv"

        # Save the data (if the file already exist it will be overwritten)
    poly_df.to_csv(path + file, index=False)
    print(f"The tax equations for year {year} are successfully saved in {file}.")

