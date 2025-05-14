#!/usr/bin/env python
# coding: utf-8

#     To work with dataframes
import pandas as pd       #  To work with arrays
import numpy as np

#     To work with files (check if a file exists on the drive, ...)
import os.path
import sys
### NOTE: If used, this absolute path needs to be set to the actual path of the package and src
# sys.path.append('c:/Users/mianji/Documents/GitHub/Income-Proxy-Model/tax_calculator/src/')

cw = os.getcwd()
sys.path.append(cw) + '\\'
# print('The working directory is:', cw)

# Import required utility functions and constants from util module
# from .util import CustomException, clinic, guide, tax_data, save_poly_xlsx, save_poly_csv, provinces, names, tax_years
from util import *

##########################################################
def tune_bpa(gross_inc, df):
    """
    Calculates the exact basic personal amount (bpa) for federal, 'NS' and 'YT'.

    Parameters
    ----------
    Refer to get_fed_tax function.

    Returns
    -------
    bpa: The exact tax exemption value.
    """
    
    ### Check to see if there are specific thresholds and rates to adjust the bpa
    ### based on the income (as of 2024 only 'NS' uses such method)
    if df['bpa'].notna().sum() == 4:
        # If the income is less than the lower tax threshold, full bpa will be granted.
        if gross_inc <= df['bpa'][1]:
            bpa = df['bpa'][0]
        # For incomes between the lower and the upper tax thresholds,
        # some reduction will be applied using the given rate on bpa.
        elif df['bpa'][1] < gross_inc < df['bpa'][2]:
            bpa = df['bpa'][0] - (gross_inc - df['bpa'][1]) * df['bpa'][3] / 100
                # Finally, if the income is greater than the upper threshold,
                # bpa would be minimum.
        else:
            bpa = df['bpa'][0] - (df['bpa'][2] - df['bpa'][1]) * df['bpa'][3] / 100

        ### Otherwise, a similar tuning but using the tax brackets thresholds might apply
        ### (as of 2024 only federal and 'YT')
    else:
        # Get the index of the last threshold based-on the number of tax rate levels.
        last_thresh_ind = df['Threshold'].notna().sum() - 1
        # The 2nd last and the last tax thresholds
        penultimat_thresh = df['Threshold'][last_thresh_ind - 1]
        last_thresh = df['Threshold'][last_thresh_ind]

        # If the income is less than the 2nd last tax threshold, full bpa
        # would be granted.
        if gross_inc <= penultimat_thresh:
            bpa = df['bpa'][0]
        # For incomes between the 2nd last and the last tax thresholds,
        # some reduction will be applied on bpa.
        elif penultimat_thresh < gross_inc < last_thresh:
            bpa = df['bpa'][0] - (gross_inc - penultimat_thresh) / \
                (last_thresh - penultimat_thresh) * df['bpa'][1]
            # And if the income is greater than the last threshold , bpa will be minimum .
        else :
            bpa = df['bpa'][0] - df['bpa'][1]

    return bpa

def get_credit(df , Federal_df , ei , exempt , cpp ) :
    '''
    Calculates the credit and cpp base contribution for every taxpayer .

    Parameters
    ----------
    df : Province or federal tax rate table ( dataframe ) .
    The other parameters are introduced in other functions like get_fed_tax .

    Returns
    -------
    credit : A deduction from the calculated tax .
    cpp_base_contrib : The ratio of paid cpp deducted from the taxable income .
    '''

    # Before returning fed_tax there are some credits to be deducted from
    # the base by federal tax rate. They are :
    # 1-bpa tuned by income
    # 2-ei
    # 3 - The CPP base contributions rate
    # The CPP base contributions rate . It defines the fraction of cpp to deduct
    # from provincial tax as a credit . The nominator is 4.95 and the
    # denominator is 5.95 , 5.7 , 5.45 , 525 and 5.1 for 2023-2019 , respectively .

    cpp_base_contrib = Federal_df['CPP_rate'][1] / Federal_df['CPP_rate'][0]

    # For QC
    if 'fed_abatement' in df:
        if df['fed_abatement'].notna().sum() > 0:
            cpp_base_contrib = Federal_df['CPP_rate'][3] / Federal_df['CPP_rate'][2]

    credit = (ei + cpp_base_contrib * cpp + exempt) * df['Rate'][0]/100

    return credit , cpp_base_contrib


def get_fed_tax(gross_inc , Federal_df , prov_df , cpp , ei ):
    '''
    Calculates federal tax.

    Parameters
    ----------
    gross_inc: The before tax to calculate the net (after-tax) income for.
    Federal_df: The federal tax information dataframe.
    prov_df: The target provice tax information dataframe.

    Returns
    -------
    fed_tax: The federal tax for the given gross income.
    '''
    fed_tax = 0

        # Every year, the federal government sets a minimum value to be exempt from tax,
        # but its value slightly differs based on the gross income value.
    fed_exempt = tune_bpa(gross_inc , Federal_df)

    credit , cpp_base_contrib = get_credit(Federal_df , Federal_df , ei , fed_exempt , cpp)

    # Canada Employment Amount is an additional credit for federal tax and Everyone
    # with a reported income can claim it (1433, 1368, 1287, 1257 and 1245 for 2024-2020,
    # respectively.)

    credit += Federal_df['employ_amount'][0] * Federal_df['Rate'][0]/100

    ### Net taxable income is gross income minus part of cpp, so adjust gross_inc
    taxable_inc = gross_inc - (1 - cpp_base_contrib) * cpp if gross_inc > cpp else 0

    if taxable_inc <= fed_exempt:
        return fed_tax

    # finds the tax bracket the taxable income belongs too
    inds = Federal_df.index[Federal_df['Threshold'] < taxable_inc]

    # If the taxable income lies in the first bracket, only one tax rate would apply
    if len(inds) == 0:
        fed_tax += taxable_inc * Federal_df.loc[0, 'Rate'] / 100
    else:
        # falling in higher brackets entails cumulative taxes (resulted from
        # lower brackets) plus the tax due to the bracket the income belongs to.
        fed_tax += Federal_df.loc[inds[-1], 'cumul_bracket']
        fed_tax += Federal_df.loc[inds[-1] + 1, 'Rate'] * (taxable_inc - Federal_df.loc[inds[-1], 'Threshold']) / 100 

    fed_tax  = fed_tax  - credit if fed_tax > credit else 0

            # As of 2024, only Quebec has an abatement rate on the federal tax
    if prov_df['fed_abatement'].notna().sum() > 0:
        fed_tax  *= 1 - prov_df['fed_abatement'][0] / 100

    return fed_tax

def get_prov_tax(gross_inc, Federal_df, prov_df, cpp, ei):
    '''
    Calculates provincial tax for a target province.

    Parameters
    ----------
    gross_inc: The before-tax to calculate the net (after-tax) income from.
    Federal_df: The federal tax information dataframe.
    prov_df: The provincial tax information dataframe.
    cpp: The amount of Canada Pension Plan to pay.
    ei: The amount of Employment Insurance to pay.
    
    Returns
    -------
    prov_tax: The provincial tax for the given gross income for a province.
    surtax: Some provinces like ON have a surtax.
    '''
    prov_tax = 0
    surtax = 0

        # Every year, provicial governments set a minimum value to be exempt from tax.

            # If there is a second row in bpa, it means bpa needs to be adjusted to income.
            # As of 2024 only 'NS' and 'YT' have this system (same as the federal tax)
    if prov_df['bpa'].notna().sum() > 1:
        prov_exempt = tune_bpa(gross_inc, prov_df)

    else:
        prov_exempt = prov_df['bpa'][0]

    # The CPP base contributions rate.
    cpp_base_contrib = Federal_df['CPP_rate'][1] / Federal_df['CPP_rate'][0]

    # For QC

    if prov_df['fed_abatement'].notna().sum() > 0:
        cpp_base_contrib = Federal_df['CPP_rate'][3] / Federal_df['CPP_rate'][2]

        ### Net taxable income is gross income minus cpp, so adjust gross_inc
    taxable_inc = gross_inc - (1 - cpp_base_contrib) * cpp if gross_inc > cpp else 0

    if taxable_inc <= prov_exempt:
        return prov_tax, surtax

        # As of 2024, only New Brunswick ('NB') has a reliaf rate for low-incomes
        # For this group, we apply the credit (prov_bpa) immediatley.
    elif prov_df['phase_out'].notna().sum() > 0:
        if taxable_inc < prov_df['phase_out'][0]:
            prov_tax -= (prov_df.loc[0, 'Rate'] * prov_df['phase_out'][1]) \
                        * (taxable_inc - prov_exempt) / 100

            prov_tax = max(0, prov_tax)

            return prov_tax, surtax

        # finds the tax bracket the taxable income belongs too
    inds = prov_df.index[prov_df['Threshold'] < taxable_inc]

        # If the taxable income lies in the first bracket, there would be only
        # one tax rate.
    if len(inds) == 0:
        prov_tax += taxable_inc * prov_df.loc[0, 'Rate'] / 100
    else:
        # falling in higher brackets entails cumulative taxes (resulted from
        # lower brackets) plus the tax due to the bracket the income belongs to.
        prov_tax += prov_df.loc[inds[-1], 'cumul_bracket']
        prov_tax += prov_df.loc[inds[-1] + 1, 'Rate'] * \
                        (taxable_inc - prov_df.loc[inds[-1], 'Threshold']) / 100

        ### Calculate the surtax of the tax (if applicable)
        ### Note: Surtaxes are calculated on basic provincial tax payable that is
        ### the provincial tax before deducting total credits.
    if prov_df['surtax_rate'].notna().sum() > 0:
        if prov_tax > prov_df['surtax_thresh'][0]:
            surtax = get_surtax(prov_df, prov_tax)
            prov_tax += surtax

        # To calculate 'health premium' (as of 2024 only required by ON and QC)
    if 'health_prem_rate' in prov_df:
        health_prem = get_health_prem(prov_df, taxable_inc)
        prov_tax += health_prem

        ### 'Quebec parental insurance plan premium' (as of 2024 only required by QC)
    if 'QPIP' in prov_df:
        qpip = get_qpip(prov_df, gross_inc)
        prov_tax += qpip
            
            
        # Now, calculate the provicial credit to deduct from prov_tax
    credit = get_credit(prov_df, Federal_df, ei, prov_exempt, cpp)
    prov_tax -= credit if prov_tax > credit else 0
        # Finally, return the provincial taxLand related surtax (if N/A, surtax = 0)

    return prov_tax, surtax
            
            
            
def get_cpp(gross_inc, cpp_rate, cpp_max, cpp_ex):
    '''
    Calculates CPP deduction.

    Parameters
    ----------
    gross_inc: The before-tax to calculate the net (after-tax) income for.
    cpp_rate: The CPP rate.
    cpp_max: The maximum pensionable earning.
    cpp_ex: The CPP basic exemption.
    
    Returns
    -------
    cpp: The CPP deduction.
    '''
    if gross_inc <= cpp_ex:
        cpp = 0
    else:
        cpp = (gross_inc - cpp_ex) * cpp_rate / 100
        if cpp > cpp_max:
            cpp = cpp_max
    return cpp

def get_cpp_additional(gross_inc, Federal_df):
    '''
    Calculates the additional CPP deduction (if any).

    Parameters
    ----------
    gross_inc: The before-tax to calculate the net (after-tax) income for.
    Federal_df: The federal tax information dataframe.
    
    Returns
    -------
    cpp_additional: The additional CPP deduction.

    '''
    cpp_additional = 0
    cpp_thresh1 = Federal_df['CPP_max_pensionable'][0]
    cpp_thresh2 = Federal_df['CPP_max_pensionable'][1]
    cpp2_rate = Federal_df['CPP_max_pensionable'][2]
    if cpp_thresh1 < gross_inc < cpp_thresh2:
        cpp_additional = (gross_inc - cpp_thresh1) * cpp2_rate / 100
    elif gross_inc >= cpp_thresh2:
        cpp_additional = (cpp_thresh2 - cpp_thresh1) * cpp2_rate / 100
    return cpp_additional

def get_ei(gross_inc, ei_rate, ei_max):
    '''
    Calculates EI deduction.

    Parameters
    ----------
    gross_inc: The before-tax to calculate the net (after-tax) income from.
    ei_rate: The EI rate.
    ei_max: The maximum insurable earning.

    Returns
    -------
    ei: The EI deduction.
    '''
    ei = gross_inc * ei_rate / 100
    if ei > ei_max:
        ei = ei_max
    return ei

def get_health_prem(prov_df, taxable_inc):
    '''
    Calculates provincial health premium (as of 2024 only applicable for ON).

    Parameters
    ----------
    prov_df: The provincial tax information dataframe.
    taxable_inc: The taxable income.

    Returns
    -------
    health_prem: The health premium that should be added to the provincial tax.
    '''
    health_prem = 0

    # Finds all the health premium thresholds the taxable income is greater than
    inds = prov_df.index[prov_df['health_prem_thresh'] < taxable_inc]

    # If the taxable income is smaller than the first thershold, len(inds) would be
    # zero and the health premium would be e as well, otherwise it needs to be
    # calculated like this
    if len(inds) > 0:
        health_prem = prov_df.loc[inds[-1], 'health_prem_limit'] + \
            (taxable_inc - prov_df.loc[inds[-1], 'health_prem_thresh']) * \
            prov_df.loc[inds[-1] + 1, 'health_prem_rate'] / 100

    # But it shouldn't be greater than the limit of the row the taxable income
    # belongs too
    if health_prem > prov_df.loc[inds[-1] + 1, 'health_prem_limit']:
        health_prem = prov_df.loc[inds[-1] + 1, 'health_prem_limit']

    return health_prem

def get_qpip(prov_df, gross_inc):
    '''
    Calculates Quebec Parental Insurance Plan Premium (QPIP) (as of 2024 only applicable
    to QC).

    Parameters
    ----------
    prov_df: The provincial tax information dataframe.
    gross_inc: The before tax to calculate the net (after-tax) income. QPIP applies on insurable earnings that include
               amounts reported on an earnings statement, or wage slip before any deductions are
               made for income tax.

    Returns
    -------
    qpip: The QPIP that should be added to the provincial tax.
    '''
    if gross_inc <= prov_df['QPIP'][0]:
        qpip = gross_inc * prov_df['QPIP'][1] / 100
    # If the gross income is bigger than the Maximum Annual Insurable Earning
    else:
        qpip = prov_df['QPIP'][0] * prov_df['QPIP'][1] / 100

    return qpip

def get_surtax(prov_df, prov_tax):
    '''
    Calculates provincial surtax (if applicable).

    Parameters
    ----------
    prov_df: The provincial tax information dataframe.
    prov_tax: The provincial tax calculated by the get_prov_tax function.
    
    Returns
    -------
    surtax: The surtax that should be added to the provincial tax.
    '''
    surtax = 0
    # As of 2024, only Ontario and Prince Edward provinces have surtax.
    # It may include more than one level (Ontario has 2).
    surtax_levels = prov_df['surtax_rate'].notna().sum()
    for i in range(surtax_levels):
        surtax += (prov_tax - prov_df['surtax_thresh'][i]) * prov_df['surtax_rate'][i] / 100
    return surtax

def gross_for_low_net(net_inc, Federal_df, prov_df):
    '''
    Calculates gross income for net incomes below minimum taxable incomes (< bpa).
    
    Parameters
    ----------
    net_inc: The after-tax to calculate the gross (before-tax) income for.
    Federal_df: The federal tax information dataframe.
    prov_df: The provincial tax information dataframe.

    Returns
    -------
    gross_inc: The before-tax income of the given after-tax income.
    '''
    cpp_rate = Federal_df['CPP_rate'][0]
    cpp_be = Federal_df['CPP_be'][0]
    ei_rate = Federal_df['EI_rate'][0]

        # Calculate the gross income using the net income and above federal and
        # provincial data. As the gross inc is unknown (but is very close to net_inc),
        # net_inc is used instead of gross income to set the condition.
    if net_inc > cpp_be:
        gross_inc = (net_inc - cpp_be * cpp_rate/100) / (1 - cpp_rate/100 - ei_rate/100)

    else:
        gross_inc = net_inc / (1 - ei_rate/100)

            # Now if the calculated gross income is greater than cpp_be, recalculate
            # it using the formula under the above 'if' condition
        if gross_inc > cpp_be:
            gross_inc = (net_inc - cpp_be * cpp_rate/100) / (1 - cpp_rate/100 - ei_rate/100)

     # print(gross_inc, net_inc, cpp_rate, ei_rate)

        # And only add 'Quebec parental insurance plan premium' (as of 2024 only for QC)
    if 'QPIP' in prov_df:
        qpip = get_qpip(prov_df, gross_inc)
        gross_inc += qpip

        # If for any reason (that is very unlikely) the calculated gross became less than
        # the net, that would be unacceptable, so, set it to the net income.
    if gross_inc < net_inc:
        gross_inc = net_inc

    return gross_inc

def gross_for_high_net(net_inc, Federal_df, prov_df):
    '''
    Calculates gross income for net incomes above a very high net income level
    (like $500000) based on this formula:
        
    X = (A + a - c + b * cum_prov - FHI * FHR * f - b * PHI * PHR ) / \
        (1 - FHR * f - b * PHR )
    where:
    A is the net income and
    a = MCPP + MEI - credit + HP + QPIP + cum_fed * f
    b = (1 + sur_rate1 + sur_rate2)
    c = (thresh_tax1*sur_rate1 + thresh_tax2*sur_rate2)

    Parameters
    ----------
    net_inc: The after tax to calculate the gross (before-tax) income for.
    Federal_df: The federal tax information dataframe for a province.
    prov_df: The provincial tax information dataframe for a province.

    Returns
    -------
    net_income: The after_tax (net) income using the given after_tax (gross) income.
    '''
        # As of 2024, only Quebec has an abatement on the federal tax.
        # f is one minus the abatement rate.
    f = 1
    if prov_df['fed_abatement'].notna().sum() > 0:
        f -= prov_df['fed_abatement'][0] / 100

        # Maximum CPP and EI are paid by such high earners
    MCPP = (Federal_df['CPP_max_pensionable'][0] - Federal_df['CPP_be'][0]) * \
           Federal_df['CPP_rate'][0] / 100
    MEI = Federal_df['EI_max_contribution'][0] * Federal_df['EI_rate'][0] / 100
    cum_fed = Federal_df['cumul_bracket'].max() * f

        # For very high earnings, the bpa is minimum
    fed_exempt = Federal_df['bpa'][0] - Federal_df['bpa'][1]

        ### ----------- let's calculate the federal and provincial credits ---------
    fed_credit, _ = get_credit(Federal_df, Federal_df, MEI, fed_exempt, MCPP)

        # Canada Employment Amount is an additional credit for federal tax and everyone
        # with a reported income can claim it (1433, 1368, 1287, 1257 and 1245 for 2024-2020)
    fed_credit += Federal_df['employ_amount'][0] * Federal_df['Rate'][0] / 100

        # If there is a second row in bpa, it means bpa needs to be adjusted to income.
        # As of 2024 only YT and NS have this system (similar to the federal bpa)
        # Note: As the income is very high, instead of gross income we use net * 2 because
        # the highest tax threshold in the tax rate bracket is smaller than that
    if prov_df['bpa'].notna().sum() > 1:
        prov_exempt = tune_bpa(net_inc * 2, prov_df)
    else:
        prov_exempt = prov_df['bpa'][0]

    prov_credit, _ = get_credit(prov_df, Federal_df, MEI, prov_exempt, MCPP)

    a = MCPP + MEI - fed_credit - prov_credit + cum_fed * f
    b = 1 # Initializes this term: b = (1 + sur_rate1 + sur_rate2)
    c = 0 # Initializes this term: c = (thresh_tax1*sur_rate1 + thresh_tax2*sur_rate2)

    ### If there is any provincial surtax for this province, take it into account.
    surtax_levels = prov_df['surtax_rate'].notna().sum()
    if surtax_levels > 0:
        for i in range(surtax_levels):
            b += prov_df['surtax_rate'][i] / 100
            c += prov_df['surtax_thresh'][i] * prov_df['surtax_rate'][i] / 100

    cum_prov = prov_df['cumul_bracket'].max()

    # Highest federal and provinical tax rate brackets' thresholds and rates
    FHI = Federal_df['Threshold'].max()
    FHR = Federal_df['Rate'].max() / 100
    PHI = prov_df['Threshold'].max()
    PHR = prov_df['Rate'].max() / 100

    gross_inc = (net_inc + a + b * cum_prov - FHI * FHR * f - b * PHI * PHR - c ) / \
                (1 - FHR * f - b * PHR)

    ### To calculate 'health premium' that as of 2024 is only
    ### required by ON and QC. For very high incomes it is always the maximum.
    if 'health_prem_rate' in prov_df:
        health_prem = prov_df['health_prem_limit'][len(prov_df['health_prem_limit']) - 1]
        gross_inc += health_prem

    ### And maximum 'Quebec parental insurance plan premium' (as of 2024 only for QC)
    if 'QPIP' in prov_df:
        qpip = get_qpip(prov_df, gross_inc)
        gross_inc += qpip

    return gross_inc

def get_net(gross_inc, Federal_df, prov, prov_df):
    '''
    Calculates the net income for a given gross income. This function is called by two
    other user-interface functions: after_tax and get_poly.
    
    Parameters
    ----------
    gross_inc: The before-tax to calculate the net (after-tax) income for.
    Federal_df: The federal tax information dataframe.
    prov_df: The provincial tax information dataframe for a province.

    Returns
    -------
    net_income: The after_tax (net) income using the given before_tax (gross) income.
    '''
    # Read the federal tax information
    # Canada Pension Plan rate (QC has a different rate)
    cpp_rate = Federal_df['CPP_rate'][0] if prov_df['province'][0] != 'QC' else Federal_df['CPP_rate'][2]
    cpp_be = Federal_df['CPP_be'][0]                # CPP basic annual exemption
    cpp_max = (Federal_df['CPP_max_pensionable'][0] - cpp_be) * cpp_rate / 100

    # Employment Insurance Rate (QC has a different rate)
    ei_rate = Federal_df['EI_rate'][0] if prov_df['province'][0] != 'QC' else Federal_df['EI_rate'][1]
    ei_max = Federal_df['EI_max_contribution'][0] * ei_rate / 100

        # Calculate the CPP deduction
    cpp = get_cpp(gross_inc, cpp_rate, cpp_max, cpp_be)

        ### Check to see if there is a 2nd additional CPP contribution required.
        ### (starting 2024 a CPP2 should be deducted)
    if Federal_df['EI_max_contribution'].notna().sum() == 3:
        cpp_additional = get_cpp_additional(gross_inc, Federal_df)
        cpp += cpp_additional

    # Calculate the EI deduction
    ei = get_ei(gross_inc, ei_rate, ei_max)

    # Calculate the federal tax
    fed_tax = get_fed_tax(gross_inc, Federal_df, prov_df, cpp, ei)

    # Calculate the provincial tax
    prov_tax, surtax = get_prov_tax(gross_inc, Federal_df, prov_df, cpp, ei)

    total_deduction = fed_tax + prov_tax + cpp + ei
    net_income = gross_inc - total_deduction

    result = {'province': prov,
              'CPP': cpp,
              'EI': ei,
              'fed_tax': fed_tax,
              'prov_tax': prov_tax,
              'surtax': surtax,
              'total_deduction': total_deduction,
              'net_income': net_income}

    return round(net_income)


def before_after_inc(df, func):
    '''
    Groups rows of the given dataframe based on year then province, calls the requested
    function over them and organizes the obtained results according to the sequence of
    corresponding rows in an array.

    Parameters:
    ----------
    func: The function to apply on df.
          df: see before_tax_combo or after_tax_combo functions.

    Returns:
    -------
    A one dimensional array of calculated before or after taxes.
    '''
    err_msg = "**** Error ***: The dataframe must have at least three columns in this \
    sequence: income, province, year. No NaN is allowed, province must be according to the \
    internationally approved abbreviations (AB, BC, MB, ...), and the year needs to be one \
    of 2020 to 2024. Moreover, income must be a positive integer or float number."
    try:
        ### First check if the df has a valid format and includes the necessary data
        if df.iloc[:, 0].isna().sum() > 0 \
           or len(df.columns) < 3 \
           or len([d for d in df.iloc[:, 1].unique() if d.upper() not in provinces]) > 0 \
           or len([d for d in df.iloc[:, 2].unique() if d not in tax_years]) > 0 \
           or df.iloc[:, 0].dtype not in ['int64', 'int32', 'float64', 'float32'] \
           or df.iloc[:, 0][df.iloc[:, 0] < 0].sum() > 0:
            print(err_msg)
            return

        derived_incs = np.empty(len(df))

        for year in tax_years:
            for prov in provinces:
                inds = df.index[(df.iloc[:, 2] == year) & (df.iloc[:, 1].str.upper() == prov)]
                if len(inds) > 0:
                    incs = func(df.iloc[inds][df.columns[0]].values, prov, year)
                    derived_incs[inds] = incs

        derived_incs = np.array(derived_incs).reshape((len(derived_incs), 1))
    
        ### To handle any possible untrapped error and guide users on troubleshooting.
    except Exception as e:
        print(err_msg, "\n")
        print("The original error is: ", "\n", e)
    else:
        return derived_incs


def before_tax_combo(df):
    '''
    Calculates the before_tax values for given combos of (net_income, province, year)
    that are organized in a dataframe.

    Parameters:
    ----------
    df: A dataframe that only has these columns (or, as the first three): net income
        (number), province (abbreviation) and year (a number between 2020 to 2024). Name of
        columns are not important.

    Returns:
    -------
    The same dataframe with an added column (before_tax) which contains the calculated
    results for all rows.
    '''
    ### Make a copy of the original dataframe
    df_copy = df.copy()
    func = before_tax_combo
    before_tax = before_after_inc(df_copy, func)
    df_copy['before_tax'] = before_tax
    return df_copy


def after_tax_combo(df):
    '''
    Calculates the after_tax values for given combos of (gross_income, province, year)
    that are organized in a dataframe.

    Parameters:
    ----------
    df: A dataframe that only has these columns (or, as the first three): net income
        (number), province (abbreviation) and year (a number between 2020 to 2024). Name of
        columns are not important.
    
        Returns:
    -------
    The same dataframe with an added column (after_tax) which contains the calculated
    results for all rows.
    '''
        ### Make a copy of the original dataframe
    df_copy = df.copy()

    func = after_tax
    after_incs = before_after_inc(func, df_copy)
    df_copy['after_tax'] = after_incs

    return df_copy

def before_tax(net_incs, prov = 'ON', year = 2023, **kwargs):
    '''
    Calculates the gross income for an array of net incomes for a specific year and province.
    
    ----------------
    Parameters:
    net incs: An array of net incomes the gross earning prov: Province will be calculated for.
    prob: Province
    year: Tax year

    Returns:
    --------
    gross_incs: A list of before_tax incomes obtained for the given after_tax incomes.
    '''

            ### First control to see if there is any typos or mistakesan the name
            ### of arguments.
    
    if len (kwargs.keys ()) > 0:
        print(f"Warning! You passed (len (kwargs.keys ())} unknown arguments to the function. \
        They are: (Id for d in kwargs.keys ()1}. For more details on how to prepare your data and \
        call the function please do as follows.\n")
        print("from tax_calculator import guide \nguide()\n")

    try:

            ### Then, check the quality of the data, if the sent prov by
            ### user is, not capital, it will be returned capitilized.       
        net_incs, prov, year = clinic(net_incs, prov, year)

            ### First load the tax rate bracket data and saved coefficients
            ### year and prov

            #######################################
            ### ----------------------- Option 1: read from the excel file ----------------
        # path = '../data/excel1_data'
        # file = 'polynomials.xlsx'
        # coeff_df = pd.read_excel(path + file, sheet_name=str(year))
        #     # The federal and provincial tax data are also needed
        # file = "tax_rates_" + str(year) + ".xlsx"
        # federal_df = pd.read_excel(path + file, sheet_name = "Federal")
        # prov_df = pd.read_excel(path + file, sheet_name = prov.upper())

            ##################################################################
            ### ----------------------- Option 1: read from the csv file ----------------
        path = '../data/tax_rates_' + str(year) + "/"
        file = 'polynomials-' + str(year) + '.csv'
        coeff_df = pd.read_csv(path + file)
            # The federal and provincial tax data are also needed
        Federal_df = pd.read_csv(path + 'Federal.csv')
        prov_df = pd.read_csv(path + prov.upper() + '.csv')
            ### ----------------------------------------------------------

        gross_incs = []
        for net_inc in net_incs:

            ### Set the polynomial's coefficients (for both low to ordinary and ordinary
            ### to high income ranges). Here 200,000 approximates the net income that
            ### corresponds to the value (350,000) set as the breakpoint in the get_poly
            ### function (to fit two separate functions over a wide range of
            ### gross_incomes).
            w = coeff_df[prov.upper() + '_low'] if net_inc < 200000 else \
                                                coeff_df[prov.upper() + '_high']

            if net_inc <= 0:
                gross_inc = 0
            ### If the net income is lower than any of the federal or provincial minimum
            ### incomes, the gross value can be directly calculated
            elif net_inc <= Federal_df['bpa'][0] or net_inc <= prov_df['bpa'][0]:
                gross_inc = gross_for_low_net(net_inc, Federal_df, prov_df)
            ### Direct calculation is also possible for very high net incomes
            elif net_inc >= 500000:
                gross_inc = gross_for_high_net(net_inc, Federal_df, prov_df)
            # For incomes in the most common (low to high) range, use the equations
            else:
                # Make the polynomial equations from the coefficients and calculate the
                # gross income
                p = np.poly1d(w)
                gross_inc = p(net_inc)
            gross_incs.append(round(gross_inc))

        ### Handle the most common and predictable user errors and communicate with
        ### users about them.
    except CustomException as e:
        print(f"Variable Error: {e}")
        print(r"For more details on how to prepare your data and call the function please \
do as follows:\n")
        print(r"tax_calculator.import_guide('nguide.vn')")

    except PermissionError as e:
        print(r"Please make sure the excel file for saving the polynomials are closed, the \
original raised error is as follows:\n")
        print(e, "\n")

        ### To handle any possible untrapped error and guide users on troubleshooting.
    except Exception as e:
        print(r"Something related to the entered data is wrong, the original raised error \
is as follows:\n")
        print(e, "\n")
        print(r"To avoid such errors please carefully follow the below instruction. In case \
errors persist report it to the Support team.\n")
        guide()

    else:
        print(f"The gross income for the net income of (net_inc) is: ", round(gross_inc))
        return gross_incs


def after_tax(gross_incs, prov = 'ON', year = 2023, **kwargs):
    '''
    calculates the after_tax income for an array of before_tax (gross) incomes for a
    specific year and province.

    Parameters
    ----------
    gross_incs: A list of before_tax incomes.
    prov: Province.
    year: Tax year.

    Returns
    -------
    after_tax: The after_tax income.
    '''
    ### First control to see if there is any typos or mistakes in the name
    ### or arguments.
    if len(kwargs.keys()) > 0:
        print(f"Warning! You passed {len(kwargs.keys())} unknown arguments to the function. \
They are: {[d for d in kwargs.keys()]}. For more details on how to prepare your data and \
call the function please do as follows.\n")
        print("from tax_calculator import guide \nguide()\n")

    try:
        ### Check the quality of the data. If the same prov by
        ### user is not capital, it will be returned capitalized.
        gross_incs, prov, year = clinic(gross_incs, prov, year)

        ### Read federal and provincial tax data for the given year from the source
        ### excel file or the tax csv files
        path = "../../data/tax_rates_" + str(year) + "/"
        Federal_df = pd.read_csv(path + 'Federal.csv')
        prov_df = pd.read_csv(path + prov.upper() + '.csv')

            # Loop over the gross income list and calculate the after-tax incomes
        net_incs = []
        for gross_inc in gross_incs:
            if gross_inc <= 0:
                net_inc = 0
            else:
                net_inc = get_net(gross_inc, Federal_df, prov.upper(), prov_df)
            net_incs.append(net_inc)

        ### Handle the most common and predictable user errors and communicate with
        ### users about them.
    except CustomException as e:
        print(f"Variable Error: {e}")
        print(r"For more details on how to prepare your data and call the function please \
do as follows.\n")
        print(r"tax_calculator.import_guide('nguide.vn')")

        ### To handle any possible untrapped error and guide users on troubleshooting.
    except Exception as e:
        print(r"Something related to the entered data is wrong, the original raised error \
is as follows.\n")
        print(e, "\n")
        print(r"For more details on how to prepare your data and call the function please \
do as follows.\n")
        print(r"tax_calculator.import_guide('nguide.vn')")

    else:
        return net_incs


def get_poly(year):
    '''
    Generates the polynomial equations for all provinces. They will be used to calculate
    the gross income for a given net income.

    Parameters
    ----------
    year: Tax year.

    Returns
    -------
    coeff_dict: Dictionary saves the obtained polynomials (their coefficients).
    '''
    try:
            ### Check the quality of the data. Note: we pass arbitrary correct values
            ### for net income and province just to have `year` tested.
        _, _, year = clinic(np.array([75000]), 'AB', year)

                ### load the tax brackets information and make the dataframes
        tables, names = tax_data(year)

            ### Generate a list of gross and driven net incomes for a province
            ### We begin with two gross income ranges as low (ordinary) and high range.
            ### The reason for this is fitting a separate polynomial equation to each
            ### range because the ordinary range is much more curvaceous especially in
            ### the lower income part. $350,000 annual gross income is set as the break
            ### point here. Experiments showed that sliding it between 200,000 and 450,000
            ### very slightly affects the calculation accuracy.
            ### In the before_tax function, where we have to choose one of the fitted
            ### polynomials (that we create here) to calculate the gross income for a
            ### given net value, we use $200,000 (annual income) as the approximate
            ### after_tax income for selecting the equation (polynomial) to be used.

        gross_incs = {}
        gross_incs['_low'] = list(range(1000, 350000, 1000))
        gross_incs['_high'] = list(range(350000, 1501000, 1000))

            # Names is a list that starts with 'Federal' and contains the abbreviation
            # for all provinces and territories of Canada like 'AB' for Alberta
        coeff_dict = {}

            # Calculates net incomes for all the gross incomes in gross_inc for
            # all territories
        for prov in names[1:]:
            for level, g_incs in gross_incs.items():
                net_incs = []
                for income in g_incs:
                    net = get_net(income, tables['Federal'], prov, tables[prov])
                    net_incs.append(net)
                    # Fit a polynomial to net_incs vs gross_incs (g_incs)
                w = np.polyfit(net_incs, g_incs, 5, rcond=None, full=False, w=None, cov=False)
                coeff_dict[prov + level] = w

    except FileNotFoundError as e:
        print("The required data source(s) doesn't exist or is in a different location, \
the original raised error is as follows.\n")
        print(e, "\n")

    else:
        # Convert polynomials dictionary to a dataframe
        poly_df = pd.DataFrame(coeff_dict)

        # Save the polynomials for all provinces in an excel sheet (same file
        # for all years.)
        # ### Note: the excel file must not be open!
        save_poly_xlsx(poly_df, year)

        # Save the polynomials for all provinces in a separate csv file
        save_poly_csv(poly_df, year)
